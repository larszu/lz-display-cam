#import <Metal/Metal.h>
#include <unordered_map>
#include <mutex>
#include "gen_struct.h"
#include "gen_metal_source.h"

static std::mutex s_Mutex;
static std::unordered_map<id<MTLCommandQueue>, id<MTLComputePipelineState>> s_Pipelines;

void LZRunMetal(void* p_CmdQ, const LZParams& p_Params, const float* p_Input, float* p_Output)
{
    id<MTLCommandQueue> queue = static_cast<id<MTLCommandQueue> >(p_CmdQ);
    id<MTLDevice> device = queue.device;
    id<MTLComputePipelineState> pipelineState;
    {
        std::unique_lock<std::mutex> lock(s_Mutex);
        const auto it = s_Pipelines.find(queue);
        if (it == s_Pipelines.end())
        {
            NSError* err = nil;
            MTLCompileOptions* options = [MTLCompileOptions new];
            id<MTLLibrary> lib = [device newLibraryWithSource:@(kLZMetalSource) options:options error:&err];
            [options release];
            if (!lib)
            {
                fprintf(stderr, "LZ Display Cam: Metal-Kern laesst sich nicht bauen: %s\n", err.localizedDescription.UTF8String);
                return;
            }
            id<MTLFunction> fn = [lib newFunctionWithName:@"LZDisplayCamKernel"];
            pipelineState = fn ? [device newComputePipelineStateWithFunction:fn error:&err] : nil;
            [lib release];
            [fn release];
            if (!pipelineState)
            {
                fprintf(stderr, "LZ Display Cam: Pipeline fehlgeschlagen\n");
                return;
            }
            s_Pipelines[queue] = pipelineState;
        }
        else
        {
            pipelineState = it->second;
        }
    }
    id<MTLBuffer> srcBuf = reinterpret_cast<id<MTLBuffer> >(const_cast<float*>(p_Input));
    id<MTLBuffer> dstBuf = reinterpret_cast<id<MTLBuffer> >(p_Output);
    id<MTLCommandBuffer> commandBuffer = [queue commandBuffer];
    commandBuffer.label = @"LZDisplayCamKernel";
    id<MTLComputeCommandEncoder> enc = [commandBuffer computeCommandEncoder];
    [enc setComputePipelineState:pipelineState];
    const int exeWidth = (int)[pipelineState threadExecutionWidth];
    [enc setBuffer:srcBuf offset:0 atIndex:0];
    [enc setBuffer:dstBuf offset:0 atIndex:8];
    [enc setBytes:&p_Params length:sizeof(LZParams) atIndex:11];
    [enc dispatchThreadgroups:MTLSizeMake((p_Params.width + exeWidth - 1) / exeWidth, p_Params.height, 1) threadsPerThreadgroup:MTLSizeMake(exeWidth, 1, 1)];
    [enc endEncoding];
    [commandBuffer commit];
}
