// CPU-Ausweichpfad: derselbe Kern wie auf der GPU, als C++ uebersetzt.
#include <cmath>
#include "gen_struct.h"
struct float3 { float x, y, z; };
static inline float3 make_float3(float a, float b, float c) { float3 r = {a, b, c}; return r; }
#define __DEVICE__ static inline
#define LZ_INPUT const float*
#define LZ_PARAMS const LZParams&
#define _floorf floorf
#define _fabs fabsf
#define _sinf sinf
#define _cosf cosf
#define _sqrtf sqrtf
#define _powf powf
#define _expf expf
#define _exp2f exp2f
#define _tanhf tanhf
#define _hypotf hypotf
#define _fmaxf fmaxf
#define _fminf fminf
static inline float _clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float _saturatef(float x) { return _clampf(x, 0.0f, 1.0f); }
static inline float _mix(float a, float b, float t) { return a + (b - a) * t; }
static inline float lz_fetch(const float* in, int w, int h, int ch, int x, int y)
{
    if (x < 0) x = 0; if (x > w - 1) x = w - 1; if (y < 0) y = 0; if (y > h - 1) y = h - 1;
    return in[((h - 1 - y) * w + x) * 4 + ch];
}
#define _tex2D(ch, x, y) lz_fetch(p_Input, p_Width, p_Height, ch, x, y)
#include "gen_cpu_body.h"

void LZRunCPU(const LZParams& P, const float* p_Input, float* p_Output, int p_Y1, int p_Y2)
{
    for (int y = p_Y1; y < p_Y2; y++)
    {
        for (int x = 0; x < P.width; x++)
        {
            const float3 c = lz_transform(P.width, P.height, x, P.height - 1 - y, p_Input, P);
            float* o = p_Output + ((long)y * P.width + x) * 4;
            o[0] = c.x; o[1] = c.y; o[2] = c.z; o[3] = 1.0f;
        }
    }
}
