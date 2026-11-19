/**
 * Safe DOM inspection, extraction, and controlled editor replacement helpers.
 * Never reads password fields, cookies, or unrelated page content.
 */

export function isSensitiveInput(element: Element | null): boolean {
  if (!element) {
    return true;
  }
  const tag = element.tagName.toLowerCase();
  if (tag === "input") {
    const typeAttr = (element.getAttribute("type") ?? "text").toLowerCase();
    if (typeAttr === "password" || typeAttr === "hidden") {
      return true;
    }
  }
  const autoComplete = (element.getAttribute("autocomplete") ?? "").toLowerCase();
  if (autoComplete.includes("password")) {
    return true;
  }
  return false;
}

export function isEditableElement(element: Element | null): element is HTMLElement {
  if (!element || isSensitiveInput(element)) {
    return false;
  }
  const tag = element.tagName.toLowerCase();
  if (tag === "textarea") {
    const ta = element as HTMLTextAreaElement;
    return !ta.disabled && !ta.readOnly;
  }
  if (tag === "input") {
    const inp = element as HTMLInputElement;
    return !inp.disabled && !inp.readOnly && inp.type === "text";
  }
  const ce = element.getAttribute("contenteditable");
  return ce === "" || ce === "true" || ce === "plaintext-only";
}

export function queryFirstEditable(doc: Document, selectors: readonly string[]): HTMLElement | null {
  for (const selector of selectors) {
    const candidate = doc.querySelector(selector);
    if (isEditableElement(candidate)) {
      return candidate;
    }
  }
  return null;
}

export function readEditorText(element: HTMLElement): string {
  if (isSensitiveInput(element)) {
    return "";
  }
  const tag = element.tagName.toLowerCase();
  if (tag === "textarea" || tag === "input") {
    return (element as HTMLTextAreaElement | HTMLInputElement).value ?? "";
  }

  // ProseMirror / Quill / rich contenteditable: extract paragraphs cleanly preserving line breaks
  const paragraphNodes = element.querySelectorAll(":scope > p, :scope > div");
  if (paragraphNodes.length > 0) {
    const lines = Array.from(paragraphNodes).map((node) => node.textContent ?? "");
    return lines.join("\n").replace(/\u00a0/g, " ");
  }
  return (element.textContent ?? "").replace(/\u00a0/g, " ");
}

export function writeEditorText(element: HTMLElement, nextText: string): boolean {
  if (!isEditableElement(element)) {
    return false;
  }
  const tag = element.tagName.toLowerCase();
  const win = element.ownerDocument.defaultView;

  if (tag === "textarea" || tag === "input") {
    try {
      const proto =
        tag === "textarea"
          ? win?.HTMLTextAreaElement?.prototype
          : win?.HTMLInputElement?.prototype;
      const descriptor = proto ? Object.getOwnPropertyDescriptor(proto, "value") : undefined;
      if (descriptor?.set) {
        descriptor.set.call(element, nextText);
      } else {
        (element as HTMLTextAreaElement).value = nextText;
      }
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    } catch {
      return false;
    }
  }

  // Rich contenteditable (ProseMirror / Quill): replace paragraph children cleanly
  try {
    const doc = element.ownerDocument;
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
    const lines = nextText.split("\n");
    for (const line of lines) {
      const p = doc.createElement("p");
      if (line.length > 0) {
        p.textContent = line;
      } else {
        p.appendChild(doc.createElement("br"));
      }
      element.appendChild(p);
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  } catch {
    return false;
  }
}
