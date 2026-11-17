#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "ExhibitStartupGate.h"
#include "UnrealClient.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/DateTime.h"

class FExhibitGameModule final : public FDefaultGameModuleImpl
{
    struct FSample
    {
        uint64 Qpc;
        int32 Lap;
        int32 Leg;
        float WorldDelta;
        double AppDelta;
        FVector Position;
        float Yaw;
        float Speed;
        uint8 Mode;
    };
    enum class EPhase { FindPlayer, WaitForGo, Warm, Walk, PhotoSettle, PhotoWait, Finished };
    EPhase Phase = EPhase::FindPlayer;
    FDelegateHandle TickHandle;
    FDelegateHandle CleanupHandle;
    FExhibitStartupGate Startup;
    TWeakObjectPtr<UWorld> StartupWorld;
    bool bRoute = false, bBypassGate = false;
    bool bCapturedCorridor = false;
    FString Dir, Events, Settings;
    TArray<FSample> Frames;
    int32 Laps = 11, Lap = 1, Leg = 0;
    bool bWaitForGo = false, bPhoto = false;
    uint64 ReadyQpc = 0, GoQpc = 0, StartQpc = 0, WarmQpc = 0, ProgressQpc = 0;
    double Best = 1e9, Yaw = -90.0;

    static FVector2D Target(int32 Index)
    {
        static const FVector2D Points[] = {{402,-890},{-117,-890},{-117,109},{-876,109},{-876,308},{-1635,308},{-1635,189},{-2154,189}};
        return Points[Index];
    }
    static double Seconds(uint64 Later, uint64 Earlier)
    {
        return static_cast<double>(Later - Earlier) * FPlatformTime::GetSecondsPerCycle64();
    }
    bool Save(const TCHAR* Name, const FString& Value) const
    {
        return FFileHelper::SaveStringToFile(Value, *FPaths::Combine(Dir, Name), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    }
    void Mark(const TCHAR* Name, uint64 Qpc, const FVector& Pos, double Angle)
    {
        Events += FString::Printf(TEXT("%s,%d,%d,%llu,%.3f,%.3f,%.3f,%.3f\n"), Name, Lap, Leg, Qpc, Pos.X, Pos.Y, Pos.Z, Angle);
    }
    void WriteSettings(UWorld* World, APlayerController* Player, ACharacter* Char, const TCHAR* Label)
    {
        int32 Width=0, Height=0;
        Player->GetViewportSize(Width, Height);
        Settings += FString::Printf(TEXT("[%s]\nqpc=%llu\nqpc_frequency=%lld\npid=%u\nmap=%s\npawn=%s\nview_target=%s\nviewport=%dx%d\nmax_walk_speed=%.2f\nrequested_laps=%d\nwait_for_go=%d\n"),
            Label, FPlatformTime::Cycles64(), FMath::RoundToInt64(1.0/FPlatformTime::GetSecondsPerCycle64()), FPlatformProcess::GetCurrentProcessId(),
            *World->GetOutermost()->GetName(), *Char->GetClass()->GetPathName(), *GetNameSafe(Player->GetViewTarget()), Width, Height,
            Char->GetCharacterMovement()->MaxWalkSpeed, Laps, bWaitForGo?1:0);
        static const TCHAR* Names[] = {
            TEXT("r.ScreenPercentage"), TEXT("r.AntiAliasingMethod"), TEXT("r.DynamicRes.OperationMode"), TEXT("r.VSync"), TEXT("t.MaxFPS"),
            TEXT("t.IdleWhenNotForeground"), TEXT("r.TSR.History.ScreenPercentage"), TEXT("r.Shadow.Virtual.MaxPhysicalPages"),
            TEXT("r.LumenScene.SurfaceCache.AtlasSize"), TEXT("r.Lumen.ScreenProbeGather.RadianceCache.ProbeResolution"), TEXT("r.Shadow.Virtual.SMRT.RayCountLocal"),
            TEXT("r.Nanite.Streaming.StreamingPoolSize"), TEXT("r.RayTracing"), TEXT("r.MegaLights.Supported"), TEXT("r.MegaLights.EnableForProject"),
            TEXT("r.MegaLights.Allowed"), TEXT("sg.ResolutionQuality"), TEXT("sg.ViewDistanceQuality"), TEXT("sg.AntiAliasingQuality"),
            TEXT("sg.ShadowQuality"), TEXT("sg.GlobalIlluminationQuality"), TEXT("sg.ReflectionQuality"), TEXT("sg.PostProcessQuality"),
            TEXT("sg.TextureQuality"), TEXT("sg.EffectsQuality"), TEXT("sg.FoliageQuality"), TEXT("sg.ShadingQuality"), TEXT("sg.LandscapeQuality") };
        for (const TCHAR* Name : Names)
        {
            const IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name);
            Settings += FString::Printf(TEXT("%s=%s\n"), Name, CVar?*CVar->GetString():TEXT("<unregistered>"));
        }
        Save(TEXT("settings.txt"),Settings);
    }
    void Finish(bool bSuccess, const TCHAR* Reason)
    {
        Phase=EPhase::Finished;
        Startup.WriteReport(Dir);
        FString Csv(TEXT("qpc,lap,leg,world_dt,app_dt,x,y,z,yaw,speed,movement_mode\n"));
        Csv.Reserve(Frames.Num()*100);
        for (const FSample& S : Frames)
        {
            Csv += FString::Printf(TEXT("%llu,%d,%d,%.9f,%.9f,%.3f,%.3f,%.3f,%.3f,%.3f,%u\n"),
                S.Qpc,S.Lap,S.Leg,S.WorldDelta,S.AppDelta,S.Position.X,S.Position.Y,S.Position.Z,S.Yaw,S.Speed,S.Mode);
        }
        const bool bFrames = Save(TEXT("frames.csv"),Csv);
        const bool bEvents = Save(TEXT("events.csv"),Events);
        Save(TEXT("result.txt"),FString::Printf(TEXT("success=%d\nreason=%s\nlap=%d\nqpc=%llu\n"),bSuccess && bFrames && bEvents?1:0,Reason,Lap,FPlatformTime::Cycles64()));
        if (bSuccess && bPhoto) { WarmQpc=FPlatformTime::Cycles64(); Phase=EPhase::PhotoSettle; return; }
        FPlatformMisc::RequestExit(false,TEXT("KDExhibitRouteComplete"));
    }
    bool Reset(ACharacter* Char,APlayerController* Player)
    {
        Char->GetCharacterMovement()->StopMovementImmediately();
        const FVector Origin(402,-73,98.15);
        if (FVector::DistSquared(Char->GetActorLocation(),Origin)>4.0 &&
            !Char->SetActorLocation(Origin,false,nullptr,ETeleportType::TeleportPhysics)) return false;
        Yaw=-90.0;
        Player->SetControlRotation(FRotator(0,Yaw,0));
        return true;
    }
    void Tick(UWorld* World,ELevelTick,float Delta)
    {
        if (Phase==EPhase::Finished || !World || !World->IsGameWorld() || !World->HasBegunPlay()) return;
        APlayerController* Player=World->GetFirstPlayerController();
        ACharacter* Char=Player?Cast<ACharacter>(Player->GetPawn()):nullptr;
        if (!Char || !Char->GetCharacterMovement()) return;
        const uint64 Now=FPlatformTime::Cycles64();
        FVector Pos=Char->GetActorLocation();
        if (!Startup.Started())
        {
            if (!World->GetOutermost()->GetName().EndsWith(TEXT("/KDStage")) || Char->GetClass()->GetName()!=TEXT("You_C"))
            {
                if (bRoute) Finish(false,TEXT("wrong_map_or_pawn"));
                return;
            }
            UGameViewportClient* Viewport = World->GetGameViewport();
            if (!Viewport) return;
            StartupWorld = World;
            Startup.Begin(*Viewport,*Player,Now,bBypassGate,bRoute || !Dir.IsEmpty());
            if (!bRoute && !Dir.IsEmpty())
                FScreenshotRequest::RequestScreenshot(FPaths::Combine(Dir,TEXT("preparing.png")),true,false);
        }
        if (World != StartupWorld.Get()) return;
        Startup.Tick(Now);
        if (!bRoute)
        {
            if (!Dir.IsEmpty() && Startup.DrawingCorridor() && !bCapturedCorridor)
            {
                FScreenshotRequest::RequestScreenshot(FPaths::Combine(Dir,TEXT("corridor_hidden.png")),true,false);
                bCapturedCorridor = true;
            }
            if (Startup.IsOpen())
            {
                if (!Dir.IsEmpty())
                {
                    Startup.WriteReport(Dir);
                    FScreenshotRequest::RequestScreenshot(FPaths::Combine(Dir,TEXT("playable.png")),true,false);
                }
                StopStartupTick();
            }
            return;
        }
        if (Phase==EPhase::PhotoSettle || Phase==EPhase::PhotoWait)
        {
            Player->SetControlRotation(FRotator(12,0,0));
            if (Phase==EPhase::PhotoSettle && Seconds(Now,WarmQpc)>0.7)
            {
                FScreenshotRequest::RequestScreenshot(FPaths::Combine(Dir,TEXT("landing_back.png")),false,false);
                Phase=EPhase::PhotoWait; WarmQpc=Now;
            }
            else if (Phase==EPhase::PhotoWait && (!FScreenshotRequest::IsScreenshotRequested() || Seconds(Now,WarmQpc)>4))
            {
                Phase=EPhase::Finished;
                FPlatformMisc::RequestExit(false,TEXT("KDExhibitRouteComplete"));
            }
            return;
        }
        if (Phase==EPhase::FindPlayer)
        {
            ReadyQpc=Now;
            Mark(TEXT("pawn_ready"),Now,Pos,Player->GetControlRotation().Yaw);
            WriteSettings(World,Player,Char,TEXT("ready"));
            if (!Reset(Char,Player)) { Finish(false,TEXT("start_reset_failed")); return; }
            Save(TEXT("ready.txt"),FString::Printf(TEXT("qpc=%llu\npid=%u\n"),ReadyQpc,FPlatformProcess::GetCurrentProcessId()));
            Phase=EPhase::WaitForGo;
            return;
        }
        if (Phase==EPhase::WaitForGo)
        {
            if (!Startup.IsOpen() || (bWaitForGo && !IFileManager::Get().FileExists(*FPaths::Combine(Dir,TEXT("go.flag"))))) return;
            GoQpc=Now;
            Mark(TEXT("go"),Now,Pos,Yaw);
            Phase=EPhase::Warm;
            WarmQpc=Now;
        }
        if (Phase==EPhase::Warm)
        {
            if (Lap>1 && Seconds(Now,WarmQpc)<2.0) return;
            StartQpc=ProgressQpc=Now; Best=1e9; Leg=0;
            Mark(TEXT("lap_start"),Now,Pos,Yaw);
            Phase=EPhase::Walk;
        }
        FVector2D DeltaXY=Target(Leg)-FVector2D(Pos.X,Pos.Y);
        double Distance=DeltaXY.Size();
        Frames.Add({Now,Lap,Leg,Delta,FApp::GetDeltaTime(),Pos,static_cast<float>(Player->GetControlRotation().Yaw),static_cast<float>(Char->GetVelocity().Size()),static_cast<uint8>(Char->GetCharacterMovement()->MovementMode.GetValue())});
        if (Distance<22.0)
        {
            Mark(TEXT("waypoint"),Now,Pos,Player->GetControlRotation().Yaw);
            if (Leg==7)
            {
                Mark(TEXT("lap_end"),Now,Pos,Player->GetControlRotation().Yaw);
                Save(TEXT("events.csv"),Events);
                if (Pos.Z>=-58) { Finish(false,TEXT("landing_height_mismatch")); return; }
                if (Lap==Laps) { WriteSettings(World,Player,Char,TEXT("final")); Finish(true,TEXT("landing")); return; }
                ++Lap; Leg=0;
                if (!Reset(Char,Player)) { Finish(false,TEXT("between_lap_reset_failed")); return; }
                Phase=EPhase::Warm; WarmQpc=Now;
                return;
            }
            ++Leg; Best=1e9; ProgressQpc=Now;
            DeltaXY=Target(Leg)-FVector2D(Pos.X,Pos.Y); Distance=DeltaXY.Size();
        }
        if (Distance<Best-3.0) { Best=Distance; ProgressQpc=Now; }
        if (Seconds(Now,ProgressQpc)>4.0 || Seconds(Now,StartQpc)>45.0)
        {
            Mark(TEXT("stall"),Now,Pos,Player->GetControlRotation().Yaw);
            WriteSettings(World,Player,Char,TEXT("stalled")); Finish(false,TEXT("stalled")); return;
        }
        const double Facing=FMath::RadiansToDegrees(FMath::Atan2(DeltaXY.Y,DeltaXY.X));
        Yaw+=FMath::Clamp(FMath::FindDeltaAngleDegrees(Yaw,Facing),-240.0*Delta,240.0*Delta);
        Player->SetControlRotation(FRotator(Leg==7?-12.0:0.0,Yaw,0));
        Char->AddMovementInput(FVector(DeltaXY.X,DeltaXY.Y,0.0)/Distance,1.0f,false);
    }
    void StopStartupTick()
    {
        Startup.End();
        if (TickHandle.IsValid()) FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);
        if (CleanupHandle.IsValid()) FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);
        TickHandle.Reset();
        CleanupHandle.Reset();
    }
    void CleanupWorld(UWorld* World, bool, bool)
    {
        if (StartupWorld.Get() == World) StopStartupTick();
    }
public:
    virtual void StartupModule() override
    {
        FDefaultGameModuleImpl::StartupModule();
        const TCHAR* Cmd=FCommandLine::Get();
        if (IsRunningDedicatedServer() || IsRunningCommandlet()) return;
        bRoute=FParse::Param(Cmd,TEXT("KDExhibitRoute"));
        TickHandle=FWorldDelegates::OnWorldPreActorTick.AddRaw(this,&FExhibitGameModule::Tick);
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddRaw(this,&FExhibitGameModule::CleanupWorld);
        if (!bRoute)
        {
            if (FParse::Value(Cmd,TEXT("KDExhibitStartupProofDir="),Dir) && !Dir.IsEmpty())
                IFileManager::Get().MakeDirectory(*Dir,true);
            return;
        }
        bBypassGate=FParse::Param(Cmd,TEXT("KDExhibitBypassGate"));
        FParse::Value(Cmd,TEXT("KDExhibitLaps="),Laps); Laps=FMath::Clamp(Laps,1,40);
        bPhoto=FParse::Param(Cmd,TEXT("KDExhibitRouteScreenshot"));
        bWaitForGo=FParse::Param(Cmd,TEXT("KDExhibitRouteWaitForGo"));
        if (!FParse::Value(Cmd,TEXT("KDExhibitRouteDir="),Dir) || Dir.IsEmpty())
            Dir=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("ExhibitRoute"),FDateTime::UtcNow().ToString(TEXT("%Y%m%d_%H%M%S")));
        IFileManager::Get().MakeDirectory(*Dir,true);
        Events=TEXT("event,lap,leg,qpc,x,y,z,yaw\n");
        Frames.Reserve(Laps*1800);
    }
    virtual void ShutdownModule() override
    {
        StopStartupTick();
        FDefaultGameModuleImpl::ShutdownModule();
    }
};
IMPLEMENT_PRIMARY_GAME_MODULE(FExhibitGameModule,myProject,"myProject");

