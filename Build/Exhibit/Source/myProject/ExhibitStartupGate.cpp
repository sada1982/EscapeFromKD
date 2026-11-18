#include "ExhibitStartupGate.h"

#include "ContentStreaming.h"
#include "Camera/PlayerCameraManager.h"
#include "DynamicRHI.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GlobalShader.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "PipelineStateCache.h"
#include "RenderTimer.h"
#include "RenderingThread.h"
#include "SceneViewExtension.h"
#include "ShaderPipelineCache.h"
#include "Styling/CoreStyle.h"
#include "UObject/UObjectGlobals.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Text/STextBlock.h"

struct FExitCullWarmup
{
    TAtomic<int32> Permutation{INDEX_NONE};
    TAtomic<uint64> Requested{0}, Completed{0};
};

static void PrepareExitCull(TSharedRef<FExitCullWarmup, ESPMode::ThreadSafe> Result)
{
    ENQUEUE_RENDER_COMMAND(KDPrepareExitCull)([Result](FRHICommandListImmediate& RHICmdList)
    {
        constexpr uint64 CookedHash = 0x13FD634121A37ED4ull;
        FShaderType* Type = FShaderType::GetShaderTypeByName(TEXT("FInstanceCull_CS"));
        FGlobalShaderMap* Map = GetGlobalShaderMap(GMaxRHIShaderPlatform);
        for (int32 Index = 0; Type && Index < Type->GetPermutationCount(); ++Index)
        {
            const TShaderRef<FShader> Shader = Map->GetShader(Type, Index);
            if (!Shader.IsValid() || Shader.GetResourceChecked().GetShaderHash(Shader->GetResourceIndex()).Hash != CookedHash) continue;
            FRHIComputeShader* Compute = Shader.GetComputeShader(false);
            if (!Compute || Compute->GetHash().Hash != CookedHash) continue;
            Result->Permutation.Store(Index);
            Result->Requested.Store(FPlatformTime::Cycles64());
            // Request the same runtime cache entry Nanite uses. Its compile event is a dispatch prerequisite.
            PipelineStateCache::GetAndOrCreateComputePipelineState(RHICmdList, {Compute, Shader.GetSpecializationConstants()});
            RHICmdList.EnqueueLambda([Result](FRHICommandListImmediate&)
            {
                Result->Completed.Store(FPlatformTime::Cycles64());
            });
            return;
        }
        Result->Completed.Store(FPlatformTime::Cycles64());
    });
}

class FCorridorWarmupView final : public FSceneViewExtensionBase
{
public:
    FCorridorWarmupView(const FAutoRegister& AutoRegister, APlayerController& InPlayer, bool bRecord)
        : FSceneViewExtensionBase(AutoRegister), LocalPlayer(&InPlayer), bProof(bRecord) {}

    void SetupViewPoint(APlayerController* Player, FMinimalViewInfo& View) override
    {
        if (Player != LocalPlayer.Get() || !Player->GetPawn()) return;
        if (!bActive)
        {
            if (bProof && (bReturning || !bHasInitial))
            {
                if (bReturning)
                {
                    ReturnedView = View.Location;
                    ReturnedRotation = View.Rotation;
                    ReturnedFov = View.FOV;
                    ++ReturnedSamples;
                }
                else
                {
                    InitialView = View.Location;
                    InitialRotation = View.Rotation;
                    InitialFov = View.FOV;
                    bHasInitial = true;
                }
            }
            return;
        }
        const FRotator CorridorRotation(0.0,bEntrance?149.1:87.06,0.0);
        const FVector EyeOffset = View.Location - Player->GetPawn()->GetActorLocation();
        const FVector CorridorPosition = bEntrance?FVector(-136.0,-858.0,98.15):FVector(-137.0,-270.0,98.15);
        View.Location = CorridorPosition + EyeOffset.RotateAngleAxis(CorridorRotation.Yaw-View.Rotation.Yaw,FVector::UpVector);
        View.Rotation = CorridorRotation;
        LastView = View.Location;
        ++Applications;
    }

    bool bActive = false, bEntrance = false, bReturning = false, bHasInitial = false;
    int32 Applications = 0;
    FVector LastView = FVector::ZeroVector;
    int32 ReturnedSamples = 0;
    FVector InitialView = FVector::ZeroVector, ReturnedView = FVector::ZeroVector;
    FRotator InitialRotation = FRotator::ZeroRotator, ReturnedRotation = FRotator::ZeroRotator;
    float InitialFov = 0.0f, ReturnedFov = 0.0f;
private:
    TWeakObjectPtr<APlayerController> LocalPlayer;
    bool bProof;
};

void FExhibitStartupGate::Begin(UGameViewportClient& InViewport, APlayerController& InPlayer, uint64 Now, bool bBypass, bool bRecord)
{
    Viewport = &InViewport;
    Player = &InPlayer;
    bRecording = bRecord;
    StartQpc = LastQpc = Now;
    DrawHandle = InViewport.OnDrawn().AddRaw(this, &FExhibitStartupGate::AfterDraw);
    if (bRecording)
    {
        Diagnostics = TEXT("qpc,wall_ms,viewport_draws,rhi_fence_ready,pso_pending,pso_active,async_packages,streaming_wanted,gt_ms,rt_ms,rhi_ms,gpu_ms,stable_frames,input_guard,view_phase\n");
        Diagnostics.Reserve(65536);
    }
    if (bBypass)
    {
        OpenQpc = Now;
        Reason = TEXT("bypass");
        return;
    }
    FParse::Value(FCommandLine::Get(),TEXT("KDStartupMaxFPS="),LoadingFpsLimit);
    if (LoadingFpsLimit != 0 && LoadingFpsLimit != 30)
    {
        LoadingFpsLimit = 0;
        LoadingCapStatus = TEXT("invalid_argument_disabled");
    }
    if (LoadingFpsLimit == 30) LoadingCapStatus = TEXT("waiting_for_pso");
    if (InPlayer.GetPawn()) StartingPawn = InPlayer.GetPawn()->GetActorLocation();
    if (bRecording)
    {
        InitialControl = InPlayer.GetControlRotation();
        InitialTarget = GetNameSafe(InPlayer.GetViewTarget());
    }
    if (!FParse::Param(FCommandLine::Get(),TEXT("KDExhibitSkipCorridorWarmup")))
        CorridorView = FSceneViewExtensions::NewExtension<FCorridorWarmupView>(InPlayer,bRecording);
    bSkipEntrance = FParse::Param(FCommandLine::Get(),TEXT("KDExhibitSkipEntranceWarmup"));
    bPreviouslyIgnored = InViewport.IgnoreInput();
    InViewport.SetIgnoreInput(true);
    InPlayer.FlushPressedKeys();
    bInputGuard = true;
    SAssignNew(Overlay, SBox)
        .Visibility(EVisibility::HitTestInvisible)
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Center)
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.025f,0.03f,0.04f,0.90f))
            .Padding(FMargin(28.0f,12.0f))
            [
                SAssignNew(LoadingText, STextBlock)
                .Text(NSLOCTEXT("KDExhibit", "StartupLoading", "準備中…"))
                .Font(FCoreStyle::GetDefaultFontStyle("Regular",18))
                .ColorAndOpacity(FLinearColor::White)
            ]
        ];
    InViewport.AddViewportWidgetContent(Overlay.ToSharedRef(), 10000);
    if (RHIGetInterfaceType() == ERHIInterfaceType::D3D12 && !FParse::Param(FCommandLine::Get(), TEXT("KDSkipExitCullPSO")))
    {
        ExitCull = MakeShared<FExitCullWarmup, ESPMode::ThreadSafe>();
        PrepareExitCull(ExitCull.ToSharedRef());
    }
}

void FExhibitStartupGate::SwitchCorridorView(EWarmView Next, uint64 Now)
{
    if (EntranceQpc && !CorridorQpc) EntranceDraws = Draws - PhaseDraws;
    CorridorView->bActive = Next != EWarmView::Return;
    CorridorView->bEntrance = Next == EWarmView::Entrance;
    if (Next == EWarmView::Entrance) EntranceQpc = Now;
    if (Next == EWarmView::Corridor) CorridorQpc = Now;
    if (Next != EWarmView::Return && !Cover.IsValid())
    {
        SAssignNew(Cover,SBorder)
            .Visibility(EVisibility::HitTestInvisible)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.025f,0.03f,0.04f,1.0f));
        Viewport->AddViewportWidgetContent(Cover.ToSharedRef(),9999);
    }
    if (Next == EWarmView::Return)
    {
        RestoreQpc = Now;
        CorridorView->bReturning = true;
        CorridorDraws = CorridorQpc ? Draws - PhaseDraws : 0;
        ViewApplications = CorridorView->Applications;
        SampledView = CorridorView->LastView;
    }
    if (Player.IsValid() && Player->PlayerCameraManager) Player->PlayerCameraManager->SetGameCameraCutThisFrame();
    PhaseDraws = Draws;
    StableFrames = 0;
    ResourceReadyQpc = 0;
    bFenceSubmitted = false;
}

void FExhibitStartupGate::AfterDraw()
{
    ++Draws;
    if (!bFenceSubmitted)
    {
        Fence.BeginFence(FRenderCommandFence::ESyncDepth::RHIThread);
        bFenceSubmitted = true;
    }
}

void FExhibitStartupGate::Tick(uint64 Now)
{
    const double SecondsPerCycle = FPlatformTime::GetSecondsPerCycle64();
    if (OpenQpc && (!bRecording || (Now - OpenQpc) * SecondsPerCycle > 1.5))
    {
        StopWatchingDraws();
        return;
    }
    const double WallMs = (Now - LastQpc) * SecondsPerCycle * 1000.0;
    LastQpc = Now;
    const bool bFenceReady = bFenceSubmitted && Fence.IsFenceComplete();
    const uint32 PsoPending = FShaderPipelineCache::NumPrecompilesRemaining();
    UpdateLoadingFrameCap(PsoPending);
    const int32 AsyncPackages = GetNumAsyncPackages();
    // Texture streaming may keep requesting optional mips on a memory-constrained display.
    // Wait for startup packages and PSOs; observe optional streaming independently.
    const bool bResourcesReady = bFenceReady && Draws > LastDraws && PsoPending == 0 && AsyncPackages == 0;
    if (bResourcesReady)
    {
        if (!ResourceReadyQpc) ResourceReadyQpc = Now;
    }
    else ResourceReadyQpc = 0;
    const bool bSettled = bResourcesReady && (WallMs <= 33.34 || (Now - ResourceReadyQpc) * SecondsPerCycle >= 1.0);
    LastDraws = Draws;
    if (bSettled)
    {
        if (StableFrames++ == 0) StableQpc = Now;
    }
    else
    {
        StableFrames = 0;
    }
    if (bRecording)
    {
        Diagnostics += FString::Printf(TEXT("%llu,%.3f,%d,%d,%u,%u,%d,%d,%.3f,%.3f,%.3f,%.3f,%d,%d,%s\n"),
            Now,WallMs,Draws,bFenceReady?1:0,PsoPending,PipelineStateCache::NumActivePrecacheRequests(),AsyncPackages,
            IStreamingManager::Get().GetNumWantingResources(),FPlatformTime::ToMilliseconds(GGameThreadTime),
            FPlatformTime::ToMilliseconds(GRenderThreadTime),FPlatformTime::ToMilliseconds(GRHIThreadTime),
            FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()),StableFrames,bInputGuard?1:0,
            RestoreQpc?TEXT("returned_room"):CorridorQpc?TEXT("corridor"):EntranceQpc?TEXT("entrance"):TEXT("room"));
    }
    if (OpenQpc) return;
    const double Elapsed = (Now - StartQpc) * SecondsPerCycle;
    if (LoadingText.IsValid())
    {
        const FText Format = Elapsed >= 30.0
            ? NSLOCTEXT("KDExhibit", "StartupLoadingLong", "準備中… 残り{0}件\n初回の準備には時間がかかる場合があります\n終了する場合はウィンドウを閉じてください")
            : NSLOCTEXT("KDExhibit", "StartupLoadingRemaining", "準備中… 残り{0}件");
        LoadingText->SetText(FText::Format(Format,FText::AsNumber(static_cast<int64>(PsoPending)+AsyncPackages)));
    }
    if (CorridorView.IsValid())
    {
        if (!EntranceQpc && !CorridorQpc && StableFrames >= 8)
        {
            SwitchCorridorView(bSkipEntrance?EWarmView::Corridor:EWarmView::Entrance,Now);
            return;
        }
        if (EntranceQpc && !CorridorQpc && !RestoreQpc)
        {
            if (StableFrames >= 8 && CorridorView->Applications > 0)
                SwitchCorridorView(EWarmView::Corridor,Now);
            return;
        }
        if (CorridorQpc && !RestoreQpc)
        {
            if (StableFrames >= 8 && CorridorView->Applications > 0)
                SwitchCorridorView(EWarmView::Return,Now);
            return;
        }
        if (RestoreQpc && Cover.IsValid())
        {
            if (bFenceReady && Draws - PhaseDraws >= 2)
            {
                Viewport->RemoveViewportWidgetContent(Cover.ToSharedRef());
                Cover.Reset();
            }
            else return;
        }
    }
    const bool bReady = (!ExitCull || ExitCull->Completed.Load() != 0) && StableFrames >= 12 && (Now - StableQpc) * SecondsPerCycle >= 0.30;
    if (bReady)
    {
        OpenQpc = Now;
        Reason = TEXT("settled");
        ReleaseInput();
        if (!bRecording) StopWatchingDraws();
    }
}

void FExhibitStartupGate::LoadingFrameCapChanged(IConsoleVariable*)
{
    if (bLoadingCapActive && !bWritingLoadingCap) bLoadingCapExternalChange = true;
}

void FExhibitStartupGate::UpdateLoadingFrameCap(uint32 PsoPending)
{
    if (LoadingFpsLimit != 30 || OpenQpc) return;
    if (bLoadingCapActive && (PsoPending == 0 || bLoadingCapExternalChange)) RestoreLoadingFrameCap();
    if (bLoadingCapActive || bLoadingCapExternalChange || PsoPending == 0) return;
    LoadingMaxFps = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"));
    if (!LoadingMaxFps) { LoadingCapStatus = TEXT("cvar_missing");return; }
    const float Current = LoadingMaxFps->GetFloat();
    if (!FMath::IsFinite(Current)) { LoadingCapStatus = TEXT("invalid_original_value");return; }
    if (Current > 0 && Current <= LoadingFpsLimit) { LoadingCapStatus = TEXT("existing_cap_already_lower");return; }
    PreviousMaxFps = LoadingMaxFps->GetString();
    PreviousMaxFpsPriority = LoadingMaxFps->GetFlags() & ECVF_SetByMask;
    LoadingMaxFpsHandle = LoadingMaxFps->OnChangedDelegate().AddRaw(this,&FExhibitStartupGate::LoadingFrameCapChanged);
    bLoadingCapActive = bWritingLoadingCap = true;
    if (PreviousMaxFpsPriority == ECVF_SetByConstructor)
        LoadingMaxFps->Set(static_cast<float>(LoadingFpsLimit),ECVF_SetByConstructor);
    else
        LoadingMaxFps->ReplaceCurrentPriorityAndTag(static_cast<float>(LoadingFpsLimit));
    bWritingLoadingCap = false;
    ++LoadingCapApplies;
    LoadingCapStatus = TEXT("active");
    if (LoadingMaxFps->GetFloat() != LoadingFpsLimit || (LoadingMaxFps->GetFlags() & ECVF_SetByMask) != PreviousMaxFpsPriority)
    {
        bLoadingCapExternalChange = true;
        RestoreLoadingFrameCap();
    }
}

void FExhibitStartupGate::RestoreLoadingFrameCap()
{
    if (!bLoadingCapActive || !LoadingMaxFps) return;
    const bool Owned = !bLoadingCapExternalChange && LoadingMaxFps->GetFloat() == LoadingFpsLimit &&
        (LoadingMaxFps->GetFlags() & ECVF_SetByMask) == PreviousMaxFpsPriority;
    LoadingMaxFps->OnChangedDelegate().Remove(LoadingMaxFpsHandle);
    LoadingMaxFpsHandle.Reset();
    bLoadingCapActive = false;
    if (Owned)
    {
        if (PreviousMaxFpsPriority == ECVF_SetByConstructor)
            LoadingMaxFps->Set(*PreviousMaxFps,ECVF_SetByConstructor);
        else
            LoadingMaxFps->ReplaceCurrentPriorityAndTag(*PreviousMaxFps);
        ++LoadingCapRestores;
        LoadingCapStatus = LoadingMaxFps->GetString() == PreviousMaxFps &&
            (LoadingMaxFps->GetFlags() & ECVF_SetByMask) == PreviousMaxFpsPriority ? TEXT("restored") : TEXT("restore_changed");
        if (LoadingCapStatus != TEXT("restored")) bLoadingCapExternalChange = true;
    }
    else
    {
        bLoadingCapExternalChange = true;
        LoadingCapStatus = TEXT("external_change_preserved");
    }
}

void FExhibitStartupGate::ReleaseInput()
{
    RestoreLoadingFrameCap();
    if (bInputGuard && Viewport.IsValid())
    {
        if (Player.IsValid() && Player->GetPawn()) ReleasedPawn = Player->GetPawn()->GetActorLocation();
        if (bRecording && Player.IsValid())
        {
            ReleasedControl = Player->GetControlRotation();
            ReleasedTarget = GetNameSafe(Player->GetViewTarget());
        }
        if (bRecording && CorridorView.IsValid())
        {
            RoomViewProof = FString::Printf(TEXT("room_view_start=%s\nroom_view_return=%s\nroom_rotation_start=%s\nroom_rotation_return=%s\nroom_fov_start=%.4f\nroom_fov_return=%.4f\nreturned_view_samples=%d\nreturned_viewport_draws=%d\n"),
                *CorridorView->InitialView.ToString(),*CorridorView->ReturnedView.ToString(),
                *CorridorView->InitialRotation.ToString(),*CorridorView->ReturnedRotation.ToString(),
                CorridorView->InitialFov,CorridorView->ReturnedFov,CorridorView->ReturnedSamples,RestoreQpc?Draws-PhaseDraws:0);
        }
        if (Cover.IsValid()) Viewport->RemoveViewportWidgetContent(Cover.ToSharedRef());
        if (Player.IsValid()) Player->FlushPressedKeys();
        Viewport->SetIgnoreInput(bPreviouslyIgnored);
        if (Overlay.IsValid()) Viewport->RemoveViewportWidgetContent(Overlay.ToSharedRef());
        bRestoreVerified = Viewport->IgnoreInput() == bPreviouslyIgnored;
    }
    bInputGuard = false;
    Cover.Reset();
    if (CorridorView.IsValid()) CorridorView->bActive = false;
    CorridorView.Reset();
    Overlay.Reset();
    LoadingText.Reset();
}

void FExhibitStartupGate::StopWatchingDraws()
{
    if (DrawHandle.IsValid() && Viewport.IsValid()) Viewport->OnDrawn().Remove(DrawHandle);
    DrawHandle.Reset();
}

void FExhibitStartupGate::End()
{
    ReleaseInput();
    StopWatchingDraws();
}

void FExhibitStartupGate::WriteReport(const FString& Directory) const
{
    if (!bRecording) return;
    const IConsoleVariable* MaxFps = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"));
    const FString CapProof = FString::Printf(TEXT("requested_fps=%d\nstatus=%s\napplies=%d\nrestores=%d\nactive=%d\nexternal_change=%d\nprevious_value=%s\nprevious_priority=%u\nfinal_value=%s\nfinal_priority=%u\n"),
        LoadingFpsLimit,*LoadingCapStatus,LoadingCapApplies,LoadingCapRestores,bLoadingCapActive?1:0,bLoadingCapExternalChange?1:0,
        *PreviousMaxFps,PreviousMaxFpsPriority,MaxFps?*MaxFps->GetString():TEXT("missing"),MaxFps?(MaxFps->GetFlags() & ECVF_SetByMask):0);
    FFileHelper::SaveStringToFile(CapProof,*FPaths::Combine(Directory,TEXT("startup_frame_cap.txt")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    FFileHelper::SaveStringToFile(Diagnostics,*FPaths::Combine(Directory,TEXT("startup.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    const IConsoleVariable* Priority = IConsoleManager::Get().FindConsoleVariable(TEXT("r.PSOPrecaching.MinPriorityForActivePrecacheRequests"));
    const FString Summary = FString::Printf(TEXT("reason=%s\nstart_qpc=%llu\nopen_qpc=%llu\ninput_restored=%d\npso_min_priority=%d\ncorridor_qpc=%llu\nreturn_qpc=%llu\ncorridor_draws=%d\ncorridor_view_applications=%d\ncorridor_eye=%s\npawn_start=%s\npawn_released=%s\n"),
        *Reason,StartQpc,OpenQpc,bRestoreVerified?1:0,Priority?Priority->GetInt():-1,CorridorQpc,RestoreQpc,CorridorDraws,ViewApplications,
        *SampledView.ToString(),*StartingPawn.ToString(),*ReleasedPawn.ToString());
    const FString ViewProof = FString::Printf(TEXT("control_start=%s\ncontrol_released=%s\nviewtarget_start=%s\nviewtarget_released=%s\n"),
        *InitialControl.ToString(),*ReleasedControl.ToString(),*InitialTarget,*ReleasedTarget);
    const FString EntranceProof = FString::Printf(TEXT("entrance_qpc=%llu\nentrance_draws=%d\n"),EntranceQpc,EntranceDraws);
    const FString CullProof = FString::Printf(TEXT("exit_cull_enabled=%d\nexit_cull_permutation=%d\nexit_cull_requested_qpc=%llu\nexit_cull_completed_qpc=%llu\n"),
        ExitCull?1:0,ExitCull?ExitCull->Permutation.Load():INDEX_NONE,ExitCull?ExitCull->Requested.Load():0,ExitCull?ExitCull->Completed.Load():0);
    FFileHelper::SaveStringToFile(Summary+ViewProof+RoomViewProof+EntranceProof+CullProof,*FPaths::Combine(Directory,TEXT("startup_result.txt")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
