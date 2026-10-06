import { Crop, LocateFixed, Maximize2, Minus, Plus, RefreshCw, RotateCcw, RotateCw, ScanSearch } from "lucide-react";
import { LocalVisualVerificationPanel, type LocalVisualExcerpt } from "./LocalVisualVerificationPanel";
import type { LocalVisualRegion } from "../../api/evidence/localVisualHttp";
import {
  evidencePageImageUrl,
  type LocatorView,
  type ProcessingRevisionPageView,
} from "../../api/evidence";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

interface OriginalEvidenceViewerProps {
  revisionId: string;
  pages: ProcessingRevisionPageView[];
  documentNames: ReadonlyMap<string, string>;
  selectedEntryId: string | null;
  selectedLocatorId: string | null;
  selectedPageLocators: LocatorView[];
  /** Changes only for explicit source navigation, not scroll-follow selection. */
  navigationKey?: string;
  onSelectPage: (entryId: string) => void;
  onReadingRotationChange?: (pageArtifactId: string, degrees: number) => void;
  unavailableRecoveryHint?: string;
  allowLocalVerification?: boolean;
  onPrepareCorrection?: (excerpt: LocalVisualExcerpt) => void;
}

function authenticatedBoxes(locators: LocatorView[], page: ProcessingRevisionPageView): LocatorView[] {
  return locators.filter(
    (locator) =>
      locator.precision === "bbox" &&
      locator.sourceDocumentVersionId === page.sourceDocumentVersionId &&
      locator.pageArtifactId === page.pageArtifactId &&
      locator.pageNumber === page.pageNumber &&
      locator.authenticity === "authenticated" &&
      locator.bbox !== null &&
      locator.coordinateFrame !== null,
  );
}

function locatorLabel(locator: LocatorView): string {
  const excerpt = locator.excerpt?.trim().replace(/\s+/g, " ");
  return excerpt ? `重点标注：${excerpt}` : "重点标注";
}

export function OriginalEvidenceViewer({
  revisionId,
  pages,
  documentNames,
  selectedEntryId,
  selectedLocatorId,
  selectedPageLocators,
  navigationKey,
  onSelectPage,
  onReadingRotationChange,
  unavailableRecoveryHint,
  allowLocalVerification = false,
  onPrepareCorrection,
}: OriginalEvidenceViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef(new Map<string, HTMLElement>());
  const locatorRefs = useRef(new Map<string, HTMLElement>());
  const regionRef = useRef<HTMLSpanElement>(null);
  const regionNavigationPending = useRef(false);
  const userScrolling = useRef(false);
  const manualScrollUntil = useRef(0);
  const programmaticScrolling = useRef(false);
  const scrollTimer = useRef<number | null>(null);
  const previousNavigationKey = useRef(navigationKey);
  const [pageNavigationSequence, setPageNavigationSequence] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [viewRotations, setViewRotations] = useState<Record<string, number>>({});
  const zoomAnchor = useRef<{ element: HTMLElement; fraction: number } | null>(null);
  const [imageAttempts, setImageAttempts] = useState<Record<string, { attempt: number; status: "loading" | "loaded" | "failed" }>>({});
  const selectedPage = pages.find((page) => page.entryId === selectedEntryId);
  const [regionMode, setRegionMode] = useState(false);
  const [regionSelection, setRegionSelection] = useState<{ pageId: string; box: LocalVisualRegion; width: number; height: number } | null>(null);
  const drag = useRef<{ pageId: string; startX: number; startY: number; width: number; height: number } | null>(null);
  const imageSizes = useRef(new Map<string, { width: number; height: number }>());
  useEffect(() => { setRegionMode(false); setRegionSelection(null); drag.current = null; }, [revisionId, selectedEntryId]);
  function rotateSelectedPage(delta: number) {
    if (!selectedPage) return;
    manualScrollUntil.current = 0;
    const key = JSON.stringify([revisionId, selectedPage.entryId]);
    const element = pageRefs.current.get(selectedPage.entryId);
    const container = scrollRef.current;
    if (element && container) {
      const rect = element.getBoundingClientRect();
      if (rect.height > 0) zoomAnchor.current = {
        element, fraction: (container.getBoundingClientRect().top - rect.top) / rect.height,
      };
    }
    const next = ((viewRotations[key] ?? 0) + delta + 360) % 360;
    setViewRotations((previous) => ({ ...previous, [key]: next }));
    setRegionSelection(null); drag.current = null;
    onReadingRotationChange?.(selectedPage.pageArtifactId, next);
  }
  const selectedBox = selectedPage
    ? authenticatedBoxes(selectedPageLocators, selectedPage).find((locator) => locator.locatorId === selectedLocatorId)
    : undefined;
  const highlightIdentity = selectedBox
    ? JSON.stringify([revisionId, selectedEntryId, selectedBox.locatorId, selectedBox.bbox, selectedBox.coordinateFrame])
    : null;

  function changeZoom(next: number) {
    if (next === zoom) return;
    manualScrollUntil.current = 0;
    const container = scrollRef.current;
    if (container !== null) {
      const top = container.getBoundingClientRect().top;
      const element = pages.map((page) => pageRefs.current.get(page.entryId))
        .find((page) => page !== undefined && page.getBoundingClientRect().bottom > top);
      if (element !== undefined) {
        const rect = element.getBoundingClientRect();
        if (rect.height > 0) zoomAnchor.current = { element, fraction: (top - rect.top) / rect.height };
      }
    }
    setZoom(next);
  }

  useLayoutEffect(() => {
    const anchor = zoomAnchor.current;
    zoomAnchor.current = null;
    const container = scrollRef.current;
    if (anchor === null || container === null || !container.contains(anchor.element)) return;
    const rect = anchor.element.getBoundingClientRect();
    programmaticScrolling.current = true;
    container.scrollTop += rect.top - container.getBoundingClientRect().top + anchor.fraction * rect.height;
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => { programmaticScrolling.current = false; }, 500);
  }, [zoom, viewRotations]);

  useLayoutEffect(() => {
    const region = regionRef.current;
    const container = scrollRef.current;
    if (!regionNavigationPending.current || region === null || container === null) return;
    regionNavigationPending.current = false;
    userScrolling.current = false;
    manualScrollUntil.current = 0;
    programmaticScrolling.current = true;
    const box = region.getBoundingClientRect();
    container.scrollTop += box.top + box.height / 2 - container.getBoundingClientRect().top - container.clientHeight / 2;
    const stage = region.closest<HTMLElement>(".original-evidence-page__stage");
    if (stage !== null) stage.scrollLeft += box.left + box.width / 2 - stage.getBoundingClientRect().left - stage.clientWidth / 2;
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => { programmaticScrolling.current = false; }, 500);
  }, [regionSelection]);

  useEffect(() => {
    if (navigationKey !== previousNavigationKey.current) {
      userScrolling.current = false;
      previousNavigationKey.current = navigationKey;
    }
    if (selectedEntryId === null || userScrolling.current) return;
    const container = scrollRef.current;
    const page = pageRefs.current.get(selectedEntryId);
    if (container === null || page === undefined) return;
    programmaticScrolling.current = true;
    const containerTop = container.getBoundingClientRect().top;
    const pageTop = page.getBoundingClientRect().top;
    const targetTop = container.scrollTop + pageTop - containerTop;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ top: targetTop, behavior: "smooth" });
    } else {
      container.scrollTop = targetTop;
    }
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => {
      programmaticScrolling.current = false;
    }, 500);
  }, [selectedEntryId, navigationKey, pageNavigationSequence]);

  useEffect(() => {
    if (selectedLocatorId === null || highlightIdentity === null || userScrolling.current) return;
    const locator = locatorRefs.current.get(selectedLocatorId);
    const container = scrollRef.current;
    if (locator === undefined || container === null) return;
    programmaticScrolling.current = true;
    const box = locator.getBoundingClientRect();
    const top = container.scrollTop + box.top + box.height / 2
      - container.getBoundingClientRect().top - container.clientHeight / 2;
    if (typeof container.scrollTo === "function") container.scrollTo({ top, behavior: "smooth" });
    else container.scrollTop = top;
    const stage = locator.closest<HTMLElement>(".original-evidence-page__stage");
    if (stage !== null) {
      stage.scrollLeft += box.left + box.width / 2 - stage.getBoundingClientRect().left - stage.clientWidth / 2;
    }
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => {
      programmaticScrolling.current = false;
    }, 500);
  }, [selectedLocatorId, highlightIdentity]);

  useEffect(
    () => () => {
      if (scrollTimer.current !== null)
        window.clearTimeout(scrollTimer.current);
    },
    [],
  );

  function handleScroll() {
    const container = scrollRef.current;
    // Result panels and image loads can cause browser scroll anchoring. Only
    // a recent user gesture may change the current clinical source page.
    if (container === null || programmaticScrolling.current || Date.now() > manualScrollUntil.current) return;
    manualScrollUntil.current = Date.now() + 220;
    userScrolling.current = true;
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => {
      userScrolling.current = false;
    }, 220);
    const viewport = container.getBoundingClientRect();
    const readingLine = viewport.top + container.clientTop + container.clientHeight / 2;
    let nearest: { entryId: string; distance: number } | null = null;
    for (const page of pages) {
      const element = pageRefs.current.get(page.entryId);
      if (element === undefined) continue;
      const rect = element.getBoundingClientRect();
      // A long page remains current while it contains the reading line.
      const distance = Math.max(rect.top - readingLine, readingLine - rect.bottom, 0);
      if (nearest === null || distance < nearest.distance) {
        nearest = { entryId: page.entryId, distance };
      }
    }
    if (nearest !== null && nearest.entryId !== selectedEntryId) {
      onSelectPage(nearest.entryId);
    }
  }

  return (
    <div className="original-evidence-viewer">
      <div
        className="original-evidence-viewer__toolbar"
        aria-label="原始资料查看工具"
      >
        <div className="original-evidence-viewer__location">
          <strong>{selectedPage ? `${documentNames.get(selectedPage.sourceDocumentVersionId) ?? "原始资料"} · 第 ${selectedPage.pageNumber} 页` : "原始资料"}</strong>
          <span>{pages.length} 页连续查看</span>
        </div>
        <div className="original-evidence-viewer__zoom">
          <button type="button" aria-label="回到当前核对页" title="回到当前核对页"
            disabled={selectedPage === undefined} onClick={() => {
              userScrolling.current = false;
              manualScrollUntil.current = 0;
              setPageNavigationSequence((sequence) => sequence + 1);
            }}>
            <LocateFixed aria-hidden="true" />
          </button>
          {allowLocalVerification && <button type="button" aria-label="圈选原件局部" title="圈选原件局部" aria-pressed={regionMode}
            disabled={!selectedPage?.imageAvailable} onClick={() => { setRegionMode(!regionMode); setRegionSelection(null); }}>
            <Crop aria-hidden="true" />
          </button>}
          <button type="button" aria-label="本页向左旋转" title="本页向左旋转"
            disabled={!selectedPage?.imageAvailable} onClick={() => rotateSelectedPage(-90)}>
            <RotateCcw aria-hidden="true" />
          </button>
          <button type="button" aria-label="本页向右旋转" title="本页向右旋转"
            disabled={!selectedPage?.imageAvailable} onClick={() => rotateSelectedPage(90)}>
            <RotateCw aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="缩小原始资料"
            title="缩小"
            disabled={Math.round(zoom * 100) <= 70}
            onClick={() => changeZoom(Math.max(0.7, Math.round(zoom * 10 - 1) / 10))}
          >
            <Minus aria-hidden="true" />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            aria-label="放大原始资料"
            title="放大"
            disabled={Math.round(zoom * 100) >= 180}
            onClick={() => changeZoom(Math.min(1.8, Math.round(zoom * 10 + 1) / 10))}
          >
            <Plus aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="原始资料适合宽度"
            title="适合宽度"
            disabled={Math.round(zoom * 100) === 100}
            onClick={() => changeZoom(1)}
          >
            <Maximize2 aria-hidden="true" />
          </button>
        </div>
      </div>
      {allowLocalVerification && selectedPage && <LocalVisualVerificationPanel
        key={JSON.stringify([revisionId, selectedPage.pageArtifactId])}
        revisionId={revisionId} pageId={selectedPage.pageArtifactId}
        onPrepareCorrection={onPrepareCorrection}
        onLocateRegion={imageSizes.current.has(JSON.stringify([revisionId, selectedPage.entryId])) ? (box) => {
          const key = JSON.stringify([revisionId, selectedPage.entryId]);
          const size = imageSizes.current.get(key)!;
          const sideways = box.clockwise_degrees === 90 || box.clockwise_degrees === 270;
          regionNavigationPending.current = true;
          setViewRotations((previous) => ({ ...previous, [key]: box.clockwise_degrees }));
          onReadingRotationChange?.(selectedPage.pageArtifactId, box.clockwise_degrees);
          setRegionSelection({ pageId: selectedPage.pageArtifactId, box,
            width: sideways ? size.height : size.width, height: sideways ? size.width : size.height });
          setRegionMode(false);
        } : undefined}
        region={regionSelection?.pageId === selectedPage.pageArtifactId ? regionSelection.box : null} />}
      <div
        ref={scrollRef}
        className="evidence-pages-scroll"
        aria-label="原始资料查看区"
        onScroll={handleScroll}
        onWheel={() => {
          programmaticScrolling.current = false;
          manualScrollUntil.current = Date.now() + 1000;
        }}
        onPointerDown={() => {
          programmaticScrolling.current = false;
          manualScrollUntil.current = Date.now() + 1000;
        }}
        onKeyDown={(event) => {
          if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(event.key)) {
            programmaticScrolling.current = false;
            manualScrollUntil.current = Date.now() + 1000;
          }
        }}
      >
        {pages.map((page, pageIndex) => {
          const selected = page.entryId === selectedEntryId;
          const imageKey = JSON.stringify([revisionId, page.entryId]);
          const rotation = viewRotations[imageKey] ?? 0;
          const sideways = rotation === 90 || rotation === 270;
          const imageState = imageAttempts[imageKey];
          const imageFailed = imageState?.status === "failed";
          const imageLoaded = imageState?.status === "loaded";
          const imageUrl = evidencePageImageUrl(revisionId, page.entryId);
          function selectOrRetry() {
            onSelectPage(page.entryId);
            if (imageFailed) {
              setImageAttempts((previous) => ({
                ...previous,
                [imageKey]: { attempt: (previous[imageKey]?.attempt ?? 0) + 1, status: "loading" },
              }));
            }
          }
          const boxes = selected && selectedLocatorId !== null
            ? authenticatedBoxes(selectedPageLocators, page)
                .filter((locator) => locator.locatorId === selectedLocatorId)
            : [];
          return (
            <article
              key={page.entryId}
              ref={(element) => {
                if (element === null) pageRefs.current.delete(page.entryId);
                else pageRefs.current.set(page.entryId, element);
              }}
              className={`original-evidence-page${selected ? " original-evidence-page--selected" : ""}`}
              aria-label={`${documentNames.get(page.sourceDocumentVersionId) ?? "原始资料"} 第 ${page.pageNumber} 页${imageFailed ? "，原图未能载入，点击重试" : ""}`}
              aria-current={selected ? "page" : undefined}
              role="button"
              tabIndex={0}
              onClick={selectOrRetry}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                selectOrRetry();
              }}
            >
              <header className="original-evidence-page__head">
                <span>
                  {documentNames.get(page.sourceDocumentVersionId) ??
                    "资料名称暂不可读取"}
                </span>
                <strong>第 {page.pageNumber} 页</strong>
              </header>
              {page.imageAvailable &&
              page.pageWidth !== null &&
              page.pageHeight !== null ? (
                <div className="original-evidence-page__stage">
                  <div
                    className="original-evidence-page__canvas"
                    onPointerDown={(event) => {
                      if (!regionMode || !selected || !imageLoaded || event.button !== 0) return;
                      const size = imageSizes.current.get(imageKey);
                      if (!size) return;
                      event.preventDefault(); event.stopPropagation();
                      const rect = event.currentTarget.getBoundingClientRect();
                      if (rect.width <= 0 || rect.height <= 0) return;
                      const width = sideways ? size.height : size.width;
                      const height = sideways ? size.width : size.height;
                      drag.current = { pageId: page.pageArtifactId, startX: Math.max(0, Math.min(width, (event.clientX - rect.left) / rect.width * width)),
                        startY: Math.max(0, Math.min(height, (event.clientY - rect.top) / rect.height * height)), width, height };
                      event.currentTarget.setPointerCapture(event.pointerId);
                    }}
                    onPointerMove={(event) => {
                      const origin = drag.current;
                      if (!origin || origin.pageId !== page.pageArtifactId) return;
                      const rect = event.currentTarget.getBoundingClientRect();
                      if (rect.width <= 0 || rect.height <= 0) return;
                      const x = Math.max(0, Math.min(origin.width, (event.clientX - rect.left) / rect.width * origin.width));
                      const y = Math.max(0, Math.min(origin.height, (event.clientY - rect.top) / rect.height * origin.height));
                      const box = { x0: Math.floor(Math.min(origin.startX, x)), y0: Math.floor(Math.min(origin.startY, y)),
                        x1: Math.ceil(Math.max(origin.startX, x)), y1: Math.ceil(Math.max(origin.startY, y)),
                        clockwise_degrees: rotation as LocalVisualRegion["clockwise_degrees"] };
                      setRegionSelection(box.x1 > box.x0 && box.y1 > box.y0 ? { pageId: origin.pageId, box, width: origin.width, height: origin.height } : null);
                    }}
                    onPointerUp={(event) => {
                      if (!drag.current) return;
                      drag.current = null;
                      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
                    }}
                    onPointerCancel={() => { drag.current = null; setRegionSelection(null); }}
                    style={{
                      width: `${zoom * 100}%`,
                      aspectRatio: sideways ? `${page.pageHeight} / ${page.pageWidth}` : `${page.pageWidth} / ${page.pageHeight}`,
                      cursor: regionMode && selected ? "crosshair" : undefined,
                    }}
                  >
                    <div style={{
                      position: "absolute", left: "50%", top: "50%",
                      width: `${sideways ? page.pageWidth / page.pageHeight * 100 : 100}%`,
                      height: `${sideways ? page.pageHeight / page.pageWidth * 100 : 100}%`,
                      transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
                    }}>
                    {!imageFailed && <img
                      src={imageState?.attempt ? `${imageUrl}?retry=${imageState.attempt}` : imageUrl}
                      alt={`第 ${page.pageNumber} 页原始资料`}
                      key={`${imageKey}:${imageState?.attempt ?? 0}`}
                      loading={selected || pageIndex === 0 ? "eager" : "lazy"}
                      decoding="async"
                      draggable={false}
                      onLoad={(event) => { imageSizes.current.set(imageKey, { width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }); setImageAttempts((previous) => ({
                        ...previous,
                        [imageKey]: { attempt: previous[imageKey]?.attempt ?? 0, status: "loaded" },
                      })); }}
                      onError={() => setImageAttempts((previous) => ({
                        ...previous,
                        [imageKey]: { attempt: previous[imageKey]?.attempt ?? 0, status: "failed" },
                      }))}
                    />}
                    {!imageFailed && boxes.map((locator) => {
                      const box = locator.bbox;
                      const frame = locator.coordinateFrame;
                      if (box === null || frame === null) return null;
                      const locatorSelected =
                        selectedLocatorId === locator.locatorId;
                      const label = locatorLabel(locator);
                      return (
                        <span
                          key={locator.locatorId}
                          ref={(element) => {
                            if (element === null) {
                              locatorRefs.current.delete(locator.locatorId);
                            } else {
                              locatorRefs.current.set(
                                locator.locatorId,
                                element,
                              );
                            }
                          }}
                          role="img"
                          className={`original-evidence-page__box${locatorSelected ? " original-evidence-page__box--selected" : ""}`}
                          aria-label={label}
                          title={label}
                          style={{
                            visibility: imageLoaded ? "visible" : "hidden",
                            left: `${(box.x0 / frame.pageWidth) * 100}%`,
                            top: `${(box.y0 / frame.pageHeight) * 100}%`,
                            width: `${((box.x1 - box.x0) / frame.pageWidth) * 100}%`,
                            height: `${((box.y1 - box.y0) / frame.pageHeight) * 100}%`,
                          }}
                        />
                      );
                    })}
                    </div>
                    {regionSelection?.pageId === page.pageArtifactId && regionSelection.box.clockwise_degrees === rotation && <span
                      ref={regionRef}
                      className="original-evidence-page__region" role="img" aria-label="待核实的圈选区域"
                      style={{ left: `${regionSelection.box.x0 / regionSelection.width * 100}%`,
                        top: `${regionSelection.box.y0 / regionSelection.height * 100}%`,
                        width: `${(regionSelection.box.x1 - regionSelection.box.x0) / regionSelection.width * 100}%`,
                        height: `${(regionSelection.box.y1 - regionSelection.box.y0) / regionSelection.height * 100}%` }} />}
                    {imageFailed && <div className="original-evidence-page__loading">
                      <div>
                        <RefreshCw aria-hidden="true" />
                        <strong>原图未能载入</strong>
                        <p>这不表示资料未提交，请点击本页重试。</p>
                        {unavailableRecoveryHint && <p>{unavailableRecoveryHint}</p>}
                      </div>
                    </div>}
                    {!imageFailed && !imageLoaded && <div className="original-evidence-page__loading">
                      <span>正在载入第 {page.pageNumber} 页原件</span>
                    </div>}
                  </div>
                </div>
              ) : (
                <div className="original-evidence-page__unavailable">
                  <ScanSearch aria-hidden="true" />
                  <strong>这一页暂时无法显示原图</strong>
                  <span>
                    {page.failureReason ??
                      "原始页图尚未形成，请在处理详情中重试这一页。"}
                  </span>
                  {unavailableRecoveryHint !== undefined && (
                    <span>{unavailableRecoveryHint}</span>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
