import { RefreshCw, Settings2 } from "lucide-react"

import { AppProviders } from "@/app/providers"
import { AppToast } from "@/components/AppToast"
import { EditSceneDialog } from "@/components/dialogs/EditSceneDialog"
import { FrameSettingsDialog } from "@/components/dialogs/FrameSettingsDialog"
import { WallRunsTimeline } from "@/components/WallRunsTimeline"
import { SceneCard } from "@/components/units/SceneCard"
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
    loading,
    refreshing,
    loadError,
    refresh,
    config,
    templates,
    nodeCards,
    wallRuns,
    frameConfig,
    nowOnWall,
    sceneNames,
    currentOnWallHeader,
    previewSrc,
    previewFilter,
    editDialogOpen,
    frameDialogOpen,
    setFrameDialogOpen,
    editingScene,
    toast,
    rowBusyId,
    showToast,
    openEdit,
    runShowNow,
    handleEditDialogOpenChange,
    commitFrameDialog,
    handleSceneSave,
  } = useWallSession()

  if (loading && !config) {
    return (
      <AppProviders>
        <div className="flex min-h-screen items-center justify-center text-[15px] text-slate-600">
          加载中…
        </div>
      </AppProviders>
    )
  }

  if (!config) {
    return (
      <AppProviders>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
          <p className="max-w-md text-[15px] text-slate-700">
            {loadError ?? "无法加载配置，请确认后端已在 5050 端口运行。"}
          </p>
          <Button type="button" onClick={() => void refresh()}>
            重试
          </Button>
        </div>
      </AppProviders>
    )
  }

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
                    onClick={() => void refresh()}
                    disabled={refreshing}
                    aria-label="刷新数据"
                  >
                    <RefreshCw
                      strokeWidth={1.5}
                      aria-hidden
                      className={refreshing ? "animate-spin" : ""}
                    />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">从服务器刷新</TooltipContent>
              </Tooltip>
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

          {loadError && (
            <p className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-4 py-2 text-[13px] text-amber-900">
              {loadError}（可点击右上角刷新重试）
            </p>
          )}

          <WallPreviewSection
            nowOnWall={nowOnWall}
            nowOnWallLabel={
              nowOnWall ? (sceneNames[nowOnWall.id] ?? nowOnWall.templateId) : undefined
            }
            frameConfig={frameConfig}
            previewSrc={previewSrc}
            previewFilter={previewFilter}
          />

          <WallRunsTimeline
            runs={wallRuns}
            sceneNames={sceneNames}
            currentOnWall={currentOnWallHeader}
          />

          <section className="space-y-5">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">绘画节点</h2>

            <ul className="grid select-none grid-cols-2 gap-2.5 sm:grid-cols-[repeat(auto-fill,minmax(10.25rem,1fr))] sm:gap-3">
              {nodeCards.map(({ template: t, scene: s }) => (
                <SceneCard
                  key={s.id}
                  scene={s}
                  displayName={t.displayName}
                  disabled={!s.enabled}
                  renderBusy={rowBusyId === s.id}
                  previewSrc={previewSrc}
                  onRenderNow={runShowNow}
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
          onCommit={(next) => void commitFrameDialog(next)}
        />

        <EditSceneDialog
          open={editDialogOpen}
          scene={editingScene}
          templates={templates}
          onOpenChange={handleEditDialogOpenChange}
          onSave={(next) => void handleSceneSave(next)}
          onError={showToast}
        />

        <AppToast message={toast} />
      </div>
    </AppProviders>
  )
}
