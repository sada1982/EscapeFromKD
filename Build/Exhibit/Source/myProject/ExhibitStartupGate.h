#pragma once

#include "CoreMinimal.h"
#include "RenderCommandFence.h"

class APlayerController;
class FCorridorWarmupView;
struct FExitCullWarmup;
class SWidget;
class UGameViewportClient;

class FExhibitStartupGate
{
public:
    void Begin(UGameViewportClient& Viewport, APlayerController& Player, uint64 Now, bool bBypass, bool bRecord);
    void Tick(uint64 Now);
    void End();
    void WriteReport(const FString& Directory) const;
    bool IsOpen() const { return OpenQpc != 0; }
    bool Started() const { return StartQpc != 0; }
    bool DrawingCorridor() const { return (EntranceQpc != 0 || CorridorQpc != 0) && RestoreQpc == 0; }

private:
    void ReleaseInput();
    void AfterDraw();
    void StopWatchingDraws();
    enum class EWarmView { Entrance, Corridor, Return };
    void SwitchCorridorView(EWarmView Next, uint64 Now);

    TWeakObjectPtr<UGameViewportClient> Viewport;
    TWeakObjectPtr<APlayerController> Player;
    TSharedPtr<SWidget> Overlay;
    TSharedPtr<SWidget> Cover;
    TSharedPtr<FCorridorWarmupView, ESPMode::ThreadSafe> CorridorView;
    TSharedPtr<FExitCullWarmup, ESPMode::ThreadSafe> ExitCull;
    FDelegateHandle DrawHandle;
    FRenderCommandFence Fence;
    uint64 StartQpc = 0, LastQpc = 0, StableQpc = 0, OpenQpc = 0;
    uint64 EntranceQpc = 0, CorridorQpc = 0, RestoreQpc = 0;
    int32 PhaseDraws = 0, EntranceDraws = 0, CorridorDraws = 0, ViewApplications = 0;
    bool bSkipEntrance = false;
    FVector StartingPawn = FVector::ZeroVector, ReleasedPawn = FVector::ZeroVector;
    FVector SampledView = FVector::ZeroVector;
    FRotator InitialControl = FRotator::ZeroRotator, ReleasedControl = FRotator::ZeroRotator;
    FString InitialTarget, ReleasedTarget;
    FString RoomViewProof;
    int32 Draws = 0, LastDraws = 0, StableFrames = 0;
    bool bFenceSubmitted = false, bInputGuard = false, bPreviouslyIgnored = false, bRecording = false, bRestoreVerified = false;
    FString Reason, Diagnostics;
};
