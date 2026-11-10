// Prueft den Metal-Kern ohne Resolve: kompiliert gen_kernel.metal zur Laufzeit, rechnet ein Bild.
//   metaltest in.raw out.raw W H frame [name=wert ...]   (raw = float32 RGBA, Zeile 0 unten)
#import <Metal/Metal.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "../gen_struct.h"
#include "../gen_defaults.inc"
#include "../gen_metal_source.h"
int main(int argc, char** argv)
{
    @autoreleasepool {
        const int W = atoi(argv[3]), H = atoi(argv[4]);
        LZParams P; memset(&P, 0, sizeof(P)); lzDefaults(P);
        P.width = W; P.height = H; P.frame = atoi(argv[5]);
        for (int i = 6; i < argc; i++) {
            std::string a(argv[i]); const size_t e = a.find('='); const std::string k = a.substr(0, e); const float v = atof(a.c_str() + e + 1);
            if (k == "p_Format") P.p_Format = (int)v; else if (k == "p_Zoom") P.p_Zoom = v; else if (k == "p_CX") P.p_CX = v; else if (k == "p_CY") P.p_CY = v;
            else if (k == "p_TiltX") P.p_TiltX = v; else if (k == "p_Moire") P.p_Moire = v; else if (k == "p_Shake") P.p_Shake = v;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSError* err = nil;
        MTLCompileOptions* opt = [MTLCompileOptions new]; opt.fastMathEnabled = YES;
        id<MTLLibrary> lib = [dev newLibraryWithSource:@(kLZMetalSource) options:opt error:&err];
        if (!lib) { fprintf(stderr, "METAL-FEHLER:\n%s\n", err.localizedDescription.UTF8String); return 1; }
        if (err) fprintf(stderr, "Warnungen:\n%s\n", err.localizedDescription.UTF8String);
        id<MTLComputePipelineState> ps = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"LZDisplayCamKernel"] error:&err];
        if (!ps) { fprintf(stderr, "Pipeline: %s\n", err.localizedDescription.UTF8String); return 1; }
        const size_t n = (size_t)W * H * 4 * sizeof(float);
        id<MTLBuffer> src = [dev newBufferWithLength:n options:MTLResourceStorageModeShared];
        id<MTLBuffer> dst = [dev newBufferWithLength:n options:MTLResourceStorageModeShared];
        FILE* f = fopen(argv[1], "rb"); fread(src.contents, 1, n, f); fclose(f);
        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
        [ce setComputePipelineState:ps];
        [ce setBuffer:src offset:0 atIndex:0]; [ce setBuffer:dst offset:0 atIndex:8];
        [ce setBytes:&P length:sizeof(P) atIndex:11];
        const int ew = (int)ps.threadExecutionWidth;
        [ce dispatchThreadgroups:MTLSizeMake((W + ew - 1) / ew, H, 1) threadsPerThreadgroup:MTLSizeMake(ew, 1, 1)];
        [ce endEncoding]; [cb commit]; [cb waitUntilCompleted];
        f = fopen(argv[2], "wb"); fwrite(dst.contents, 1, n, f); fclose(f);
        printf("ok %dx%d %.1f ms GPU\n", W, H, (cb.GPUEndTime - cb.GPUStartTime) * 1000.0);
    }
    return 0;
}
