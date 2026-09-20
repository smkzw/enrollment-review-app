import { Maximize2, Minus, Plus, RefreshCw, RotateCcw, RotateCw, ScanSearch } from "lucide-react";
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
  unavailableRecoveryHint?: string;
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
  unavailableRecoveryHint,
}: OriginalEvidenceViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef(new Map<string, HTMLElement>());
  const locatorRefs = useRef(new Map<string, HTMLElement>());
  const userScrolling = useRef(false);
  const programmaticScrolling = useRef(false);
  const scrollTimer = useRef<number | null>(null);
  const previousNavigationKey = useRef(navigationKey);
  const [zoom, setZoom] = useState(1);
  const [viewRotations, setViewRotations] = useState<Record<string, number>>({});
  const zoomAnchor = useRef<{ element: HTMLElement; fraction: number } | null>(null);
  const [imageAttempts, setImageAttempts] = useState<Record<string, { attempt: number; status: "loading" | "loaded" | "failed" }>>({});
  const selectedPage = pages.find((page) => page.entryId === selectedEntryId);
  function rotateSelectedPage(delta: number) {
    if (!selectedPage) return;
    const key = JSON.stringify([revisionId, selectedPage.entryId]);
    const element = pageRefs.current.get(selectedPage.entryId);
    const container = scrollRef.current;
    if (element && container) {
      const rect = element.getBoundingClientRect();
      if (rect.height > 0) zoomAnchor.current = {
        element, fraction: (container.getBoundingClientRect().top - rect.top) / rect.height,
      };
    }
    setViewRotations((previous) => ({ ...previous, [key]: ((previous[key] ?? 0) + delta + 360) % 360 }));
  }
  const selectedBox = selectedPage
    ? authenticatedBoxes(selectedPageLocators, selectedPage).find((locator) => locator.locatorId === selectedLocatorId)
    : undefined;
  const highlightIdentity = selectedBox
    ? JSON.stringify([revisionId, selectedEntryId, selectedBox.locatorId, selectedBox.bbox, selectedBox.coordinateFrame])
    : null;

  function changeZoom(next: number) {
    if (next === zoom) return;
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
  }, [selectedEntryId, navigationKey]);

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
    if (container === null || programmaticScrolling.current) return;
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
      <div
        ref={scrollRef}
        className="evidence-pages-scroll"
        aria-label="原始资料查看区"
        onScroll={handleScroll}
        onWheel={() => {
          programmaticScrolling.current = false;
        }}
        onPointerDown={() => {
          programmaticScrolling.current = false;
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
                    style={{
                      width: `${zoom * 100}%`,
                      aspectRatio: sideways ? `${page.pageHeight} / ${page.pageWidth}` : `${page.pageWidth} / ${page.pageHeight}`,
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
                      onLoad={() => setImageAttempts((previous) => ({
                        ...previous,
                        [imageKey]: { attempt: previous[imageKey]?.attempt ?? 0, status: "loaded" },
                      }))}
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
