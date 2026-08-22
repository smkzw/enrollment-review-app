import { Minus, Plus, ScanSearch } from "lucide-react";
import {
  evidencePageImageUrl,
  type LocatorView,
  type ProcessingRevisionPageView,
} from "../../api/evidence";
import { useEffect, useRef, useState } from "react";

interface OriginalEvidenceViewerProps {
  revisionId: string;
  pages: ProcessingRevisionPageView[];
  documentNames: ReadonlyMap<string, string>;
  selectedEntryId: string | null;
  selectedLocatorId: string | null;
  selectedPageLocators: LocatorView[];
  onSelectPage: (entryId: string) => void;
}

function authenticatedBoxes(locators: LocatorView[]): LocatorView[] {
  return locators.filter(
    (locator) =>
      locator.precision === "bbox" &&
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
  onSelectPage,
}: OriginalEvidenceViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef(new Map<string, HTMLElement>());
  const locatorRefs = useRef(new Map<string, HTMLElement>());
  const userScrolling = useRef(false);
  const programmaticScrolling = useRef(false);
  const scrollTimer = useRef<number | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
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
  }, [selectedEntryId]);

  useEffect(() => {
    if (selectedLocatorId === null || userScrolling.current) return;
    const locator = locatorRefs.current.get(selectedLocatorId);
    if (locator === undefined) return;
    programmaticScrolling.current = true;
    locator.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });
    if (scrollTimer.current !== null) window.clearTimeout(scrollTimer.current);
    scrollTimer.current = window.setTimeout(() => {
      programmaticScrolling.current = false;
    }, 500);
  }, [selectedLocatorId]);

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
    const top = container.getBoundingClientRect().top;
    let nearest: { entryId: string; distance: number } | null = null;
    for (const page of pages) {
      const element = pageRefs.current.get(page.entryId);
      if (element === undefined) continue;
      const distance = Math.abs(element.getBoundingClientRect().top - top);
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
        aria-label="原始资料缩放"
      >
        <span>{pages.length} 页连续查看</span>
        <div className="original-evidence-viewer__zoom">
          <button
            type="button"
            aria-label="缩小原始资料"
            title="缩小"
            onClick={() => setZoom((value) => Math.max(0.7, value - 0.1))}
          >
            <Minus aria-hidden="true" />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            aria-label="放大原始资料"
            title="放大"
            onClick={() => setZoom((value) => Math.min(1.8, value + 0.1))}
          >
            <Plus aria-hidden="true" />
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
        {pages.map((page) => {
          const selected = page.entryId === selectedEntryId;
          const boxes = selected && selectedLocatorId !== null
            ? authenticatedBoxes(selectedPageLocators)
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
              aria-label={`${documentNames.get(page.sourceDocumentVersionId) ?? "原始资料"} 第 ${page.pageNumber} 页`}
              aria-current={selected ? "page" : undefined}
              role="button"
              tabIndex={0}
              onClick={() => onSelectPage(page.entryId)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                onSelectPage(page.entryId);
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
                      aspectRatio: `${page.pageWidth} / ${page.pageHeight}`,
                    }}
                  >
                    <img
                      src={evidencePageImageUrl(revisionId, page.entryId)}
                      alt={`第 ${page.pageNumber} 页原始资料`}
                      loading="eager"
                      decoding="async"
                    />
                    {boxes.map((locator) => {
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
                          className={`original-evidence-page__box${locatorSelected ? " original-evidence-page__box--selected" : ""}`}
                          aria-label={label}
                          title={label}
                          style={{
                            left: `${(box.x0 / frame.pageWidth) * 100}%`,
                            top: `${(box.y0 / frame.pageHeight) * 100}%`,
                            width: `${((box.x1 - box.x0) / frame.pageWidth) * 100}%`,
                            height: `${((box.y1 - box.y0) / frame.pageHeight) * 100}%`,
                          }}
                        />
                      );
                    })}
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
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
