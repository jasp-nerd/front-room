import type { ReactNode } from "react";
import { liveRoom } from "./live/feed";
import { DemoSurface } from "./surfaces/demo/DemoSurface";
import { HomeSurface } from "./surfaces/home/HomeSurface";
import { HowSurface } from "./surfaces/how/HowSurface";
import { PhoneSurface } from "./surfaces/phone/PhoneSurface";
import { RoomSurface } from "./surfaces/room/RoomSurface";
import { StudioSurface } from "./surfaces/studio/StudioSurface";
import { JoinScreen } from "./surfaces/tv/JoinScreen";
import { LiveTv } from "./surfaces/tv/LiveTv";
import { type TvState, TvSurface } from "./surfaces/tv/TvSurface";
import { FitStage } from "./ui/FitStage";
import { ShowcaseBar } from "./ui/ShowcaseBar";

function tvState(params: URLSearchParams): TvState {
  return params.get("state") === "base" ? "base" : "origin";
}

/**
 * Each surface has its own path so the demo, screenshots and video can open any of them directly:
 * `/how`, `/tv?state=join|base|origin` (or `/tv?live=1` to follow a real room), `/join?room=4821`, `/phones`, `/phone?fan=rob&sheet=why`, `/room`, `/studio`, `/demo?live=1`.
 */
export function App() {
  const { pathname, search } = window.location;
  const params = new URLSearchParams(search);
  if (pathname === "/" || pathname === "") return <HomeSurface />;
  if (pathname.startsWith("/how")) return <HowSurface />;
  if (pathname.startsWith("/demo")) return <DemoSurface />;
  if (pathname.startsWith("/room")) return <RoomSurface />;
  if (pathname.startsWith("/studio")) return <StudioSurface />;
  if (pathname.startsWith("/phone") || pathname.startsWith("/join")) return <PhoneSurface />;
  // The TV pages fill the window. A real room's TV (`?live=1`) is just the picture; the example screens say what
  // they are and lead to the real thing.
  if (liveRoom())
    return (
      <TvPage>
        <LiveTv />
      </TvPage>
    );
  if (params.get("state") === "join")
    return (
      <TvPage
        line="The TV before kick-off. Everyone on the sofa scans the code to get their own helper."
        action={{ href: "/join?room=4821", label: "Try joining" }}
      >
        <JoinScreen />
      </TvPage>
    );
  return (
    <TvPage
      line="The shared TV after Okafor's goal, showing what the room agreed on."
      action={{ href: "/demo?live=1", label: "Watch it live" }}
    >
      <TvSurface state={tvState(params)} />
    </TvPage>
  );
}

function TvPage({
  line,
  action,
  children,
}: {
  line?: string;
  action?: { href: string; label: string };
  children: ReactNode;
}) {
  return (
    <FitStage
      width={1920}
      height={1080}
      header={line ? <ShowcaseBar line={line} {...(action ? { action } : {})} /> : undefined}
    >
      {children}
    </FitStage>
  );
}
