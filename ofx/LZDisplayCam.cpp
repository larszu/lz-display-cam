// LZ Display Cam - OpenFX-Plugin fuer DaVinci Resolve.
// Die Bildrechnung kommt aus resolve/LZ_DisplayCam.dctl (gen.py erzeugt daraus Metal- und CPU-Kern).
#include "LZDisplayCam.h"
#include <cstring>
#include <memory>
#include "ofxsProcessing.h"
#include "gen_struct.h"

#define kPluginName "LZ Display Cam"
#define kPluginGrouping "LZ Medienproduktion"
#define kPluginDescription "Lässt eine Bildschirmaufnahme aussehen, als hätte eine Handkamera das Display abgefilmt: Moiré aus Panel- und Sensorraster, Spiegelung, Refresh-Streifen, Handwackeln mit Rolling Shutter, Objektiv und Sensorrauschen."
#define kPluginIdentifier "de.zumpelars.DisplayCam"
#define kPluginVersionMajor 1
#define kPluginVersionMinor 1

extern void LZRunMetal(void* p_CmdQ, const LZParams& p_Params, const float* p_Input, float* p_Output);
extern void LZRunCPU(const LZParams& p_Params, const float* p_Input, float* p_Output, int p_Y1, int p_Y2);

class LZProcessor : public OFX::ImageProcessor
{
public:
    explicit LZProcessor(OFX::ImageEffect& p_Instance) : OFX::ImageProcessor(p_Instance), _srcImg(nullptr) {}
    virtual void processImagesMetal()
    {
        LZRunMetal(_pMetalCmdQ, _params, static_cast<const float*>(_srcImg->getPixelData()), static_cast<float*>(_dstImg->getPixelData()));
    }
    virtual void multiThreadProcessImages(OfxRectI p_Win)
    {
        const OfxRectI& b = _dstImg->getBounds();
        LZRunCPU(_params, static_cast<const float*>(_srcImg->getPixelData()), static_cast<float*>(_dstImg->getPixelData()), p_Win.y1 - b.y1, p_Win.y2 - b.y1);
    }
    void setSrcImg(OFX::Image* p_Img) { _srcImg = p_Img; }
    LZParams _params;
private:
    OFX::Image* _srcImg;
};

class LZDisplayCam : public OFX::ImageEffect
{
public:
    explicit LZDisplayCam(OfxImageEffectHandle p_Handle) : ImageEffect(p_Handle)
    {
        m_DstClip = fetchClip(kOfxImageEffectOutputClipName);
        m_SrcClip = fetchClip(kOfxImageEffectSimpleSourceClipName);
    }
    virtual void render(const OFX::RenderArguments& p_Args);
    virtual void changedParam(const OFX::InstanceChangedArgs& p_Args, const std::string& p_ParamName);
private:
    OFX::Clip* m_DstClip;
    OFX::Clip* m_SrcClip;
};

#include "gen_presets.inc"

void LZDisplayCam::changedParam(const OFX::InstanceChangedArgs& p_Args, const std::string& p_ParamName)
{
    if (p_ParamName == "lookApply" || (p_ParamName == "look" && p_Args.reason == OFX::eChangeUserEdit))
    {
        int idx = 0;
        fetchChoiceParam("look")->getValue(idx);
        if (idx >= 0 && idx < kLZPresetCount)
        {
            beginEditBlock("LZ Display Cam Look");
            lzApplyPreset(this, idx);
            endEditBlock();
        }
    }
}

void LZDisplayCam::render(const OFX::RenderArguments& p_Args)
{
    if (m_DstClip->getPixelDepth() != OFX::eBitDepthFloat || m_DstClip->getPixelComponents() != OFX::ePixelComponentRGBA)
    {
        OFX::throwSuiteStatusException(kOfxStatErrUnsupported);
    }
    std::unique_ptr<OFX::Image> dst(m_DstClip->fetchImage(p_Args.time));
    std::unique_ptr<OFX::Image> src(m_SrcClip->fetchImage(p_Args.time));
    if (!dst.get() || !src.get() || src->getPixelDepth() != dst->getPixelDepth() || src->getPixelComponents() != dst->getPixelComponents())
    {
        OFX::throwSuiteStatusException(kOfxStatErrValue);
    }
    const OfxRectI& b = src->getBounds();
    const double t = p_Args.time;
    LZProcessor proc(*this);
    LZParams& P = proc._params;
    memset(&P, 0, sizeof(P));
#include "gen_fetch.inc"
    P.width = b.x2 - b.x1;
    P.height = b.y2 - b.y1;
    P.frame = (int)(t + 0.5);
    // Fusion kennt die Bildrate am Clip nicht (kOfxStatErrMissingHostFeature) -> Effekt, dann 30.
    double fps = 0.0;
    try { fps = m_SrcClip->getFrameRate(); } catch (...) { fps = 0.0; }
    if (fps <= 1.0) { try { fps = getFrameRate(); } catch (...) { fps = 0.0; } }
    P.p_Fps = (fps > 1.0) ? (float)fps : 30.0f;

    proc.setDstImg(dst.get());
    proc.setSrcImg(src.get());
    proc.setGPURenderArgs(p_Args);
    proc.setRenderWindow(p_Args.renderWindow);
    proc.process();
}

using namespace OFX;

LZDisplayCamFactory::LZDisplayCamFactory() : OFX::PluginFactoryHelper<LZDisplayCamFactory>(kPluginIdentifier, kPluginVersionMajor, kPluginVersionMinor) {}

void LZDisplayCamFactory::describe(OFX::ImageEffectDescriptor& p_Desc)
{
    p_Desc.setLabels(kPluginName, kPluginName, kPluginName);
    p_Desc.setPluginGrouping(kPluginGrouping);
    p_Desc.setPluginDescription(kPluginDescription);
    p_Desc.addSupportedContext(eContextFilter);
    p_Desc.addSupportedContext(eContextGeneral);
    p_Desc.addSupportedBitDepth(eBitDepthFloat);
    p_Desc.setSingleInstance(false);
    p_Desc.setHostFrameThreading(false);
    p_Desc.setSupportsMultiResolution(false);
    p_Desc.setSupportsTiles(false);
    p_Desc.setTemporalClipAccess(false);
    p_Desc.setRenderTwiceAlways(false);
    p_Desc.setSupportsMultipleClipPARs(false);
#ifdef __APPLE__
    p_Desc.setSupportsMetalRender(true);
#endif
    p_Desc.setNoSpatialAwareness(false);
}

void LZDisplayCamFactory::describeInContext(OFX::ImageEffectDescriptor& p_Desc, OFX::ContextEnum)
{
    ClipDescriptor* srcClip = p_Desc.defineClip(kOfxImageEffectSimpleSourceClipName);
    srcClip->addSupportedComponent(ePixelComponentRGBA);
    srcClip->setTemporalClipAccess(false);
    srcClip->setSupportsTiles(false);
    srcClip->setIsMask(false);
    ClipDescriptor* dstClip = p_Desc.defineClip(kOfxImageEffectOutputClipName);
    dstClip->addSupportedComponent(ePixelComponentRGBA);
    dstClip->setSupportsTiles(false);

    PageParamDescriptor* page = p_Desc.definePageParam("Controls");
    {
        ChoiceParamDescriptor* p = p_Desc.defineChoiceParam("look");
        p->setLabels("Look", "Look", "Look");
        p->setHint("Fertige Abstimmung. Setzt Aufstellung, Handkamera, Display, Objektiv und Sensor; Bildausschnitt und Keyframes der Kamerafahrt bleiben.");
        for (int i = 0; i < kLZPresetCount; i++) p->appendOption(kLZPresetNames[i]);
        p->setDefault(0);
        p->setAnimates(false);
        page->addChild(*p);
        PushButtonParamDescriptor* b = p_Desc.definePushButtonParam("lookApply");
        b->setLabels("Look erneut anwenden", "Look erneut anwenden", "Look erneut anwenden");
        b->setHint("Setzt alle Look-Regler auf die gewählte Abstimmung zurück.");
        page->addChild(*b);
    }
#include "gen_describe.inc"
}

ImageEffect* LZDisplayCamFactory::createInstance(OfxImageEffectHandle p_Handle, ContextEnum)
{
    return new LZDisplayCam(p_Handle);
}

void OFX::Plugin::getPluginIDs(PluginFactoryArray& p_FactoryArray)
{
    static LZDisplayCamFactory factory;
    p_FactoryArray.push_back(&factory);
}
