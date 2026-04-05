import { Settings2 } from "lucide-react"

import { AppProviders } from "@/app/providers"
import { AppToast } from "@/components/AppToast"
import { EditSceneDialog } from "@/components/dialogs/EditSceneDialog"
import { FrameSettingsDialog } from "@/components/dialogs/FrameSettingsDialog"
import { PlaybackTimeline } from "@/components/PlaybackTimeline"
import { SceneCard } from "@/components/scenes/SceneCard"
import { WallPreviewSection } from "@/components/wall/WallPreviewSection"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useWallSession } from "@/hooks/useWallSession"

export default function App() {
  const {
    scenes,
    editDialogOpen,
    frameDialogOpen,
    setFrameDialogOpen,
    editingScene,
    toast,
    rowBusyId,
    frameConfig,
    mergedRunLogs,
    nowOnWall,
    previewSrc,
    previewFilter,
    commitFrameDialog,
    openEdit,
    runRenderNow,
    handleScheduleSave,
    handleEditDialogOpenChange,
  } = useWallSession()

  return (
    <AppProviders>
      <div className="min-h-screen px-4 pb-24 pt-8 sm:px-6 lg:px-10">
        <div className="mx-auto max-w-4xl space-y-10">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="font-display text-[1.75rem] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[2rem]">
              壁上此刻
            </h1>
            <div className="flex flex-wrap gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-11 w-11 shrink-0 rounded-full text-slate-600 transition-[color,background-color,transform] hover:bg-slate-200/55 hover:text-slate-800 active:scale-[0.96] focus-visible:ring-slate-400/45 [&_svg]:!h-5 [&_svg]:!w-5"
                    onClick={() => setFrameDialogOpen(true)}
                    aria-label="画框设置"
                  >
                    <Settings2 strokeWidth={1.5} aria-hidden />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">画框设置</TooltipContent>
              </Tooltip>
            </div>
          </header>

          <WallPreviewSection
            nowOnWall={nowOnWall}
            frameConfig={frameConfig}
            previewSrc={previewSrc}
            previewFilter={previewFilter}
          />

          <PlaybackTimeline
            scenes={scenes}
            currentOnWall={nowOnWall ? { id: nowOnWall.id, name: nowOnWall.name } : null}
            runLogs={mergedRunLogs}
          />

          <section className="space-y-5">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">场景</h2>

            <ul className="grid select-none grid-cols-2 gap-2.5 sm:grid-cols-[repeat(auto-fill,minmax(10.25rem,1fr))] sm:gap-3">
              {scenes.map((u) => (
                <SceneCard
                  key={u.id}
                  scene={u}
                  disabled={!u.enabled}
                  renderBusy={rowBusyId === u.id}
                  previewSrc={previewSrc}
                  onRenderNow={runRenderNow}
                  onEdit={openEdit}
                />
              ))}
            </ul>
          </section>
        </div>

        <FrameSettingsDialog
          open={frameDialogOpen}
          onOpenChange={setFrameDialogOpen}
          committedConfig={frameConfig}
          onCommit={commitFrameDialog}
        />

        <EditSceneDialog
          open={editDialogOpen}
          scene={editingScene}
          onOpenChange={handleEditDialogOpenChange}
          onSave={handleScheduleSave}
        />

        <AppToast message={toast} />
      </div>
    </AppProviders>
  )
}
