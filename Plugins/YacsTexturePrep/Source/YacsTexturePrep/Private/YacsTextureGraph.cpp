#include "YacsTextureGraph.h"
#include "YacsTextureTools.h"
#include "Engine/Texture2D.h"
#include "TextureGraph.h"
#include "TG_Graph.h"
#include "TG_Node.h"
#include "TG_Pin.h"
#include "Expressions/Input/TG_Expression_Texture.h"
#include "Expressions/Input/TG_Expression_Scalar.h"
#include "Expressions/Input/TG_Expression_Color.h"
#include "Expressions/Procedural/TG_Expression_Gradient.h"
#include "Expressions/Procedural/TG_Expression_Transform.h"
#include "Expressions/Maths/TG_Expression_Blend.h"
#include "Expressions/Maths/TG_Expression_Clamp.h"
#include "Expressions/Maths/TG_Expression_Maths_OneInput.h"
#include "Expressions/Maths/TG_Expression_Maths_TwoInputs.h"
#include "Expressions/Maths/TG_Expression_Maths_ThreeInputs.h"
#include "Expressions/Filter/TG_Expression_Blur.h"
#include "Expressions/Color/TG_Expression_Grayscale.h"
#include "Expressions/Adjustment/TG_Expression_NormalFromHeightMap.h"
#include "Expressions/Output/TG_Expression_Output.h"
#include "UObject/Package.h"

namespace
{
// Scalar/color constants must be connected input nodes: Texture Graph resets
// unconnected variant defaults when an input changes the common type to Texture.
struct FBuilder
{
    UTG_Graph* Graph;
    bool bValid = true;
    template<class T, class F> UTG_Node* Node(F Init)
    {
        T* Expression = NewObject<T>(Graph);
        Init(*Expression);
        UTG_Node* Result = Graph->CreateExpressionNode(Expression);
        bValid &= Result != nullptr;
        return Result;
    }
    template<class T> UTG_Node* Node() { return Node<T>([](T&) {}); }
    void Link(UTG_Node* From, UTG_Node* To, const TCHAR* Input, const TCHAR* Output = TEXT("Output"))
    {
        FTG_Name A(Output), B(Input);
        bValid &= From && To && Graph->Connect(*From, A, *To, B);
    }
    void Constant(UTG_Node* To, const TCHAR* Input, float Value)
    {
        auto* N = Node<UTG_Expression_Scalar>([=](auto& E) { E.Scalar = Value; });
        Link(N, To, Input, TEXT("ValueOut"));
    }
    UTG_Node* Clamp(UTG_Node* Input, float Min = 0, float Max = 1)
    {
        auto* N = Node<UTG_Expression_Clamp>([=](auto& E) { E.MinValue = Min; E.MaxValue = Max; });
        Constant(N, TEXT("MinValue"), Min); Constant(N, TEXT("MaxValue"), Max);
        Link(Input, N, TEXT("Input")); return N;
    }
    UTG_Node* Multiply(UTG_Node* Input, float Gain)
    {
        auto* N = Node<UTG_Expression_Multiply>([=](auto& E) { E.Input2 = Gain; });
        Constant(N, TEXT("Input2"), Gain);
        Link(Input, N, TEXT("Input1")); return N;
    }
    UTG_Node* Blur(UTG_Node* Input)
    {
        auto* N = Node<UTG_Expression_Blur>([](auto& E) { E.Radius = 32; E.Strength = 1; });
        Link(Input, N, TEXT("Input")); return N;
    }
    UTG_Node* GrayscaleTexture(UTG_Node* Input)
    {
        auto* N = Node<UTG_Expression_Grayscale>();
        Link(Input, N, TEXT("Input")); return N;
    }
    UTG_Node* Seam(UTG_Node* Input, float Width)
    {
        if (Width == 0) return Input;
        for (int Axis = 0; Axis < 2; ++Axis)
        {
            auto* Gradient = Node<UTG_Expression_Gradient>([=](auto& E) {
                E.Rotation = Axis ? EGradientRotation::GTR_90 : EGradientRotation::GTR_0;
            });
            auto* Signed = Node<UTG_Expression_Subtract>([](auto& E) { E.Input2 = 1.0f; });
            Constant(Signed, TEXT("Input2"), 1);
            Link(Multiply(Gradient, 2), Signed, TEXT("Input1"));
            auto* Abs = Node<UTG_Expression_Abs>(); Link(Signed, Abs, TEXT("Input"));
            auto* Mask = Node<UTG_Expression_SmoothStep>([=](auto& E) { E.Min = 1 - 2 * Width; E.Max = 1.0f; });
            Constant(Mask, TEXT("Min"), 1 - 2 * Width); Constant(Mask, TEXT("Max"), 1);
            Link(Abs, Mask, TEXT("Input"));
            auto* Mirror = Node<UTG_Expression_Transform>([=](auto& E) { E.MirrorX = Axis == 0; E.MirrorY = Axis == 1; });
            Link(Input, Mirror, TEXT("Input"));
            auto* Blend = Node<UTG_Expression_Blend>([](auto& E) { E.Opacity = 0.5f; });
            Link(Input, Blend, TEXT("Background")); Link(Mirror, Blend, TEXT("Foreground")); Link(Mask, Blend, TEXT("Mask"));
            Input = Blend;
        }
        return Input;
    }
};
}

bool BuildYacsTextureGraph(UYacsTextureJob& Job, UTexture2D* Source, FString& Error)
{
    UPackage* Package = CreatePackage(*(Job.Folder / TEXT("TG_YACS_MaterialPrep")));
    Job.Graph = NewObject<UTextureGraph>(Package, TEXT("TG_YACS_MaterialPrep"), RF_Public | RF_Standalone);
    Job.Graph->Construct(TEXT("TG_YACS_MaterialPrep"));
    Job.Graph->Graph()->Reset();
    FBuilder B{Job.Graph->Graph()};
    const auto& R = Job.Recipe;
    auto* Input = B.Node<UTG_Expression_Texture>([=](auto& E) { E.Source = Source; });
    Input->GetExpression()->SetTitleName(TEXT("AI_Source"));
    auto* Gray = B.Node<UTG_Expression_Grayscale>(); B.Link(Input, Gray, TEXT("Input"));
    // Bounded ratio removes broad illumination only; it cannot recover true albedo.
    auto* Divide = B.Node<UTG_Expression_Divide>();
    B.Link(Input, Divide, TEXT("Input1")); B.Link(B.Clamp(B.Blur(Gray), 0.1f, 1), Divide, TEXT("Input2"));
    auto* Corrected = B.Multiply(Divide, 0.5f);
    auto* Delight = B.Node<UTG_Expression_Lerp>([&](auto& E) { E.LerpValue = R.DeLightStrength; });
    B.Constant(Delight, TEXT("LerpValue"), R.DeLightStrength);
    B.Link(Input, Delight, TEXT("Input1")); B.Link(Corrected, Delight, TEXT("Input2"));
    auto* Gain = B.Node<UTG_Expression_Multiply>([&](auto& E) { E.Input2 = R.ColorGain; });
    auto* Color = B.Node<UTG_Expression_Color>([&](auto& E) { E.Color = R.ColorGain; });
    B.Link(Color, Gain, TEXT("Input2"), TEXT("ValueOut"));
    B.Link(Delight, Gain, TEXT("Input1"));
    auto* BaseColor = B.Seam(B.Clamp(Gain), R.SeamBlendWidth);
    auto* Luma = B.Node<UTG_Expression_Grayscale>(); B.Link(BaseColor, Luma, TEXT("Input"));
    // Materialize once before branching to Normal and the exported height.
    auto* Height = B.GrayscaleTexture(B.Multiply(Luma, R.HeightStrength));
    auto* Normal = B.Node<UTG_Expression_NormalFromHeightMap>([&](auto& E) {
        E.Strength = R.NormalStrength; E.Offset = 1.0f / R.Resolution;
    });
    B.Link(Height, Normal, TEXT("Input"));
    auto* Roughness = B.Node<UTG_Expression_Add>([&](auto& E) { E.Input2 = R.RoughnessMin; });
    B.Constant(Roughness, TEXT("Input2"), R.RoughnessMin);
    B.Link(B.Multiply(Luma, R.RoughnessMax - R.RoughnessMin), Roughness, TEXT("Input1"));
    auto* Macro = B.Node<UTG_Expression_Lerp>([&](auto& E) { E.Input1 = 0.5f; E.LerpValue = R.MacroVariation; });
    B.Constant(Macro, TEXT("Input1"), 0.5f); B.Constant(Macro, TEXT("LerpValue"), R.MacroVariation);
    B.Link(B.Seam(B.Blur(Luma), R.SeamBlendWidth), Macro, TEXT("Input2"));
    const TCHAR* Roles[] = {TEXT("BaseColor"), TEXT("Height"), TEXT("Normal"), TEXT("Roughness"), TEXT("MacroMask")};
    // Materialize variant math as texture-valued grayscale before Output.
    // The explicit texture pin avoids scalar/variant output fallback to black.
    UTG_Node* Outputs[] = {BaseColor, Height, Normal, B.GrayscaleTexture(Roughness), B.GrayscaleTexture(Macro)};
    for (int I = 0; I < 5; ++I)
    {
        const bool bColor = I == 0;
        const auto Compression = I == 2 ? TC_Normalmap : bColor ? TC_Default : TC_Masks;
        auto* Out = B.Node<UTG_Expression_Output>([&](auto& E) {
            E.OutputSettings.Set(R.Resolution, R.Resolution, FName(Roles[I]), FName(Job.Folder),
                ETG_TextureFormat::BGRA8, ETG_TexturePresetType::None, Compression, TEXTUREGROUP_World, bColor);
            E.OutputSettings.OutputName = FName(Roles[I]);
        });
        Out->GetExpression()->SetTitleName(FName(Roles[I]));
        B.Link(Outputs[I], Out, TEXT("Source"));
    }
    if (!B.bValid) { Error = TEXT("Texture Graph node/pin connection failed"); return false; }
    Job.Graph->MarkPackageDirty();
    return true;
}
