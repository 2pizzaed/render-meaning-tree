var traceData = [];
var draggedTraceIndex = null;
// Индекс шага, который Reason признал ошибочным: следующее действие заменит его.
var pendingErrorStepIndex = null;
// Имя действия трассы, чьи кнопки подсвечены во фрагменте кода.
var highlightedTraceAction = null;
var traceActionIdsByName = buildTraceActionIdsByName();
// LOQI, поданный в reasoner последним запуском Reason/Hint.
var lastReasonerLoqi = null;
var lastReasonerLoqiSource = "";
var loqiMatches = [];
var loqiMatchIndex = -1;

function buildTraceActionIdsByName() {
    const scriptTag = document.getElementById("answer_objects");
    const idsByName = new Map();
    try {
        const answerObjects = scriptTag && scriptTag.textContent.trim() ? JSON.parse(scriptTag.textContent) : {};
        for (const [actionId, actionName] of Object.entries(answerObjects)) {
            if (typeof actionName !== "string" || !actionName) continue;
            if (!idsByName.has(actionName)) idsByName.set(actionName, []);
            idsByName.get(actionName).push(actionId);
        }
    } catch (error) {
        console.error("Error parsing answer_objects:", error);
    }
    return idsByName;
}

function findCodeButtonsForTraceAction(actionName) {
    const actionIds = traceActionIdsByName.get(actionName) || [];
    return Array.from(document.querySelectorAll(".injected-button[data-action-id]"))
        .filter((button) => actionIds.includes(button.getAttribute("data-action-id")));
}

function applyTraceHighlight() {
    document.querySelectorAll(".injected-button.trace-highlighted").forEach((button) => {
        button.classList.remove("trace-highlighted");
    });
    if (highlightedTraceAction === null) return [];
    const buttons = findCodeButtonsForTraceAction(highlightedTraceAction);
    buttons.forEach((button) => button.classList.add("trace-highlighted"));
    return buttons;
}

function toggleTraceHighlight(actionName) {
    highlightedTraceAction = highlightedTraceAction === actionName ? null : actionName;
    const buttons = applyTraceHighlight();
    updateTraceView();
    buttons[0]?.scrollIntoView({behavior: "smooth", block: "center", inline: "nearest"});
}

function showTraceActionInSourceMap(actionName) {
    const button = findCodeButtonsForTraceAction(actionName)[0];
    const nodeId = button?.getAttribute("data-node-id");
    if (!nodeId) {
        alert(`No code button found for trace action: ${actionName}`);
        return;
    }
    const nodeType = button.getAttribute("data-node-type") || null;
    if (!navigateToSourceMapNode(nodeId, nodeType)) {
        const typeSuffix = nodeType === null ? "" : ` (${nodeType})`;
        alert(`Node #${nodeId}${typeSuffix} was not found in Source Map.`);
    }
}

function setPendingErrorStep(index) {
    pendingErrorStepIndex = Number.isInteger(index) && index >= 0 && index < traceData.length ? index : null;
}

function appendTraceAction(actionName) {
    if (pendingErrorStepIndex !== null) {
        // Непроверенные шаги после ошибочного тоже отбрасываются.
        traceData.splice(pendingErrorStepIndex);
    }
    traceData.push(actionName);
    setPendingErrorStep(null);
    updateTraceView();
}

function checkedTracePrefix() {
    return pendingErrorStepIndex !== null ? traceData.slice(0, pendingErrorStepIndex) : traceData;
}

function finalNodeMetaValues(finalNode, name) {
    if (!finalNode || !Array.isArray(finalNode.metadata)) return [];
    return finalNode.metadata
        .filter((entry) => entry && entry.name === name && entry.value != null)
        .map((entry) => String(entry.value));
}

function renderExplanationNodes(nodes) {
    if (!Array.isArray(nodes) || nodes.length === 0) return "";
    const items = nodes.map((node) => {
        if (!node) return "";
        const mutedClass = node.muted ? " muted" : "";
        if (node.kind === "group") {
            const inner = renderExplanationNodes(node.children || []);
            if (!inner) return "";
            const label = node.skill
                ? `<div class="reason-expl-group-label">${escapeHtml(node.skill)}</div>`
                : "";
            return `<li class="reason-expl-group${mutedClass}">${label}${inner}</li>`;
        }
        if (node.kind === "more") {
            if (!node.text) return "";
            return `<li class="reason-expl-more${mutedClass}">${escapeHtml(node.text)}</li>`;
        }
        if (!node.text) return "";
        const skill = node.skill
            ? `<span class="reason-expl-skill">${escapeHtml(node.skill)}</span>`
            : "";
        return `<li class="reason-expl-leaf${mutedClass}">${escapeHtml(node.text)}${skill}</li>`;
    }).filter(Boolean);
    if (items.length === 0) return "";
    return `<ul class="reason-expl">${items.join("")}</ul>`;
}

function updateTraceView() {
    const list = document.getElementById("trace-list");
    if (!list) return;
    list.innerHTML = "";

    if (highlightedTraceAction !== null && !traceData.includes(highlightedTraceAction)) {
        highlightedTraceAction = null;
        applyTraceHighlight();
    }

    if (traceData.length === 0) {
        const empty = document.createElement("div");
        empty.className = "trace-empty";
        empty.textContent = "Trace is empty. Click rendered action buttons to add steps.";
        list.appendChild(empty);
        return;
    }

    traceData.forEach((traceAction, index) => {
        list.appendChild(createTraceItem(traceAction, index));
    });
}

function createTraceItem(traceAction, index) {
    const item = document.createElement("div");
    item.className = index === pendingErrorStepIndex ? "trace-item trace-item-error" : "trace-item";
    if (index === pendingErrorStepIndex) {
        item.title = "Incorrect step: the next selected action will replace it";
    }
    item.draggable = true;
    item.dataset.index = String(index);

    const handle = document.createElement("span");
    handle.className = "trace-drag-handle";
    handle.innerHTML = '<i class="ri-draggable" aria-hidden="true"></i>';
    handle.title = "Drag trace step";

    const label = document.createElement("span");
    label.className = "trace-label";
    label.textContent = traceAction;
    label.title = traceAction;

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "trace-delete-button";
    deleteButton.title = "Delete trace step";
    deleteButton.setAttribute("aria-label", "Delete trace step");
    deleteButton.innerHTML = '<i class="ri-close-line" aria-hidden="true"></i>';
    deleteButton.addEventListener("click", () => removeTraceItem(index));

    const hasCodeButton = findCodeButtonsForTraceAction(traceAction).length > 0;

    const highlightButton = document.createElement("button");
    highlightButton.type = "button";
    highlightButton.className = traceAction === highlightedTraceAction
        ? "trace-item-icon-button trace-highlight-button active"
        : "trace-item-icon-button trace-highlight-button";
    highlightButton.title = hasCodeButton ? "Highlight action button in code" : "No action button in code";
    highlightButton.setAttribute("aria-label", "Highlight action button in code");
    highlightButton.setAttribute("aria-pressed", String(traceAction === highlightedTraceAction));
    highlightButton.innerHTML = '<i class="ri-mark-pen-line" aria-hidden="true"></i>';
    highlightButton.disabled = !hasCodeButton;
    highlightButton.addEventListener("click", () => toggleTraceHighlight(traceAction));

    const treeButton = document.createElement("button");
    treeButton.type = "button";
    treeButton.className = "trace-item-icon-button trace-tree-button";
    treeButton.title = "Show action node in Source Map";
    treeButton.setAttribute("aria-label", "Show action node in Source Map");
    treeButton.innerHTML = '<i class="ri-node-tree" aria-hidden="true"></i>';
    treeButton.disabled = !hasCodeButton || typeof SOURCE_MAP_DATA === "undefined" || !SOURCE_MAP_DATA?.origin;
    treeButton.addEventListener("click", () => showTraceActionInSourceMap(traceAction));

    item.append(handle, label, highlightButton, treeButton, deleteButton);
    item.addEventListener("dragstart", handleTraceDragStart);
    item.addEventListener("dragend", handleTraceDragEnd);
    item.addEventListener("dragover", handleTraceDragOver);
    item.addEventListener("drop", handleTraceDrop);

    return item;
}

function clearTrace() {
    traceData = [];
    setPendingErrorStep(null);
    updateTraceView();
    renderReasoningResult(null);
}

function removeTraceItem(index) {
    traceData.splice(index, 1);
    setPendingErrorStep(null);
    updateTraceView();
    renderReasoningResult(null);
}

function handleTraceDragStart(event) {
    draggedTraceIndex = Number(event.currentTarget.dataset.index);
    event.currentTarget.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(draggedTraceIndex));
}

function handleTraceDragEnd(event) {
    draggedTraceIndex = null;
    event.currentTarget.classList.remove("dragging");
    document.getElementById("trace-list")?.classList.remove("drag-over");
}

function handleTraceDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    document.getElementById("trace-list")?.classList.add("drag-over");
}

function handleTraceDrop(event) {
    event.preventDefault();
    document.getElementById("trace-list")?.classList.remove("drag-over");

    const targetIndex = Number(event.currentTarget.dataset.index);
    if (!Number.isInteger(draggedTraceIndex) || !Number.isInteger(targetIndex) || draggedTraceIndex === targetIndex) {
        return;
    }

    const [movedAction] = traceData.splice(draggedTraceIndex, 1);
    traceData.splice(targetIndex, 0, movedAction);
    setPendingErrorStep(null);
    updateTraceView();
    renderReasoningResult(null);
}

async function copyTraceJson() {
    try {
        await navigator.clipboard.writeText(JSON.stringify(traceData, null, 2));
    } catch (error) {
        alert(`Could not copy trace JSON: ${error}`);
    }
}

async function pasteTraceJson() {
    let clipboardText = "";
    try {
        clipboardText = await navigator.clipboard.readText();
    } catch (error) {
        alert(`Could not read trace JSON from clipboard: ${error}`);
        return;
    }

    let parsedTrace;
    try {
        parsedTrace = JSON.parse(clipboardText);
    } catch (error) {
        alert(`Trace JSON has invalid syntax: ${error.message}`);
        return;
    }

    if (!isTraceJson(parsedTrace)) {
        alert("Trace JSON format error: expected an array of strings.");
        return;
    }

    traceData = parsedTrace;
    setPendingErrorStep(null);
    updateTraceView();
    renderReasoningResult(null);
}

function isTraceJson(value) {
    return Array.isArray(value) && value.every((item) => typeof item === "string");
}

async function reasonTrace() {
    const button = document.getElementById("reason-button");
    if (!button || traceData.length === 0) {
        renderReasoningResult({ok: false, error: "Select at least one trace action before running Reason."});
        return;
    }

    button.disabled = true;
    button.textContent = "Reasoning...";
    try {
        const response = await fetch("/reason-trace", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                code: document.querySelector('textarea[name="code"]')?.value || "",
                language: document.querySelector('select[name="language"]')?.value || "java",
                target_language: document.querySelector('select[name="target_language"]')?.value || "",
                trace: traceData,
            }),
        });
        const payload = await response.json();
        rememberReasonerLoqi(payload, "Reason");
        setPendingErrorStep(payload.ok ? payload.failedStepIndex : null);
        updateTraceView();
        renderReasoningResult(payload);
    } catch (error) {
        renderReasoningResult({ok: false, error: String(error)});
    } finally {
        button.disabled = false;
        button.textContent = "Reason";
    }
}

async function requestHint() {
    const button = document.getElementById("hint-button");
    if (!button) return;

    button.disabled = true;
    button.textContent = "Hinting...";
    try {
        const response = await fetch("/hint-trace", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                code: document.querySelector('textarea[name="code"]')?.value || "",
                language: document.querySelector('select[name="language"]')?.value || "java",
                target_language: document.querySelector('select[name="target_language"]')?.value || "",
                trace: checkedTracePrefix(),
            }),
        });
        const payload = await response.json();
        rememberReasonerLoqi(payload, "Hint");
        if (!payload.ok) {
            renderReasoningResult(payload);
            return;
        }
        if (payload.finished) {
            renderHintResult("correct", "Program is fully traced: no next action, trace unchanged.");
            return;
        }
        appendTraceAction(payload.action);
        renderHintResult("unknown", `Hint: added ${payload.action}`);
    } catch (error) {
        renderReasoningResult({ok: false, error: String(error)});
    } finally {
        button.disabled = false;
        button.textContent = "Hint";
    }
}

function renderHintResult(status, message) {
    renderReasoningResult(null);
    const statusBox = document.getElementById("reason-status");
    if (!statusBox) return;
    statusBox.className = `reason-alert ${status}`;
    statusBox.textContent = message;
    scrollToReasonStatus();
}

function scrollToReasonStatus() {
    // Сообщение стоит первым в прокручиваемой области трассы.
    document.querySelector(".trace-workspace")?.scrollTo({top: 0, behavior: "smooth"});
}

function openCorrectTrace() {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/tracing";
    form.target = "_blank";
    form.style.display = "none";
    appendHiddenInput(form, "code", document.querySelector('textarea[name="code"]')?.value || "");
    appendHiddenInput(form, "language", document.querySelector('select[name="language"]')?.value || "java");
    document.body.appendChild(form);
    form.submit();
    form.remove();
}

function appendHiddenInput(form, name, value) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
}

function renderReasoningResult(payload) {
    const statusBox = document.getElementById("reason-status");
    const variablesBox = document.getElementById("reason-variables");
    if (!statusBox || !variablesBox) return;
    statusBox.className = "reason-alert hidden";
    statusBox.innerHTML = "";
    variablesBox.className = "reason-variables hidden";
    variablesBox.innerHTML = "";
    if (!payload) return;

    if (!payload.ok) {
        statusBox.className = "reason-alert error";
        statusBox.textContent = payload.error || "Reasoning failed.";
        scrollToReasonStatus();
        return;
    }

    const reasoning = payload.reasoning || {};
    const status = reasoning.status || "unknown";
    statusBox.className = `reason-alert ${status}`;
    const headerLines = [
        `<div class="reason-alert-title"><strong>${status === "correct" ? "Correct" : status === "error" ? "Incorrect" : "Unknown result"}</strong>`,
    ];
    if (reasoning.hasException) {
        const names = (reasoning.exceptionNames || []).filter(Boolean).join(", ");
        headerLines.push(`<div class="reason-line">An exception occurred${names ? `: ${escapeHtml(names)}` : "."}</div>`);
    }
    headerLines.push("</div>");

    const badgeParts = [];
    const finalNodeId = finalNodeMetaValues(reasoning.finalNode, "id")[0] || "";
    if (finalNodeId) {
        badgeParts.push(`<span class="reason-badge"><strong>id</strong> ${escapeHtml(finalNodeId)}</span>`);
    }
    const lineText = finalNodeMetaValues(reasoning.finalNode, "line").join(", ");
    if (lineText) {
        badgeParts.push(`<span class="reason-badge"><strong>line</strong> ${escapeHtml(lineText)}</span>`);
    }
    const skillText = (reasoning.skills || []).filter(Boolean).join(", ");
    if (skillText) {
        badgeParts.push(`<span class="reason-badge"><strong>skill</strong> ${escapeHtml(skillText)}</span>`);
    }
    const explanationHtml = reasoning.explanationView
        ? renderExplanationNodes(reasoning.explanationView.children || [])
        : (reasoning.explanations || [])
            .map((text) => `<div class="reason-line">Explanation: ${escapeHtml(text)}</div>`)
            .join("");
    statusBox.innerHTML = [
        '<div class="reason-alert-header">',
        headerLines.join(""),
        badgeParts.length > 0 ? `<div class="reason-alert-badges">${badgeParts.join("")}</div>` : "",
        "</div>",
        explanationHtml,
    ].join("");

    const variables = reasoning.variables || {};
    const entries = Object.entries(variables);
    if (entries.length > 0) {
        variablesBox.className = "reason-variables";
        variablesBox.innerHTML = `<table><thead><tr><th>Variable</th><th>Value</th></tr></thead><tbody>${
            entries.map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(String(value))}</td></tr>`).join("")
        }</tbody></table>`;
    }
    scrollToReasonStatus();
}

// --- LOQI Viewer ---
const LOQI_IDENTIFIER_CHAR = "[A-Za-z0-9_]";

function rememberReasonerLoqi(payload, source) {
    if (!payload || typeof payload.loqi !== "string") return;
    lastReasonerLoqi = payload.loqi;
    lastReasonerLoqiSource = `${source}, ${new Date().toLocaleTimeString()}`;
    const button = document.getElementById("loqi-button");
    if (button) button.disabled = false;
    if (isLoqiModalOpen()) renderLoqiModal();
}

function isLoqiModalOpen() {
    const modal = document.getElementById("loqi-modal");
    return Boolean(modal && !modal.classList.contains("hidden"));
}

function openLoqiModal() {
    const modal = document.getElementById("loqi-modal");
    if (!modal || lastReasonerLoqi === null) return;
    modal.classList.remove("hidden");
    renderLoqiModal();
    const input = document.getElementById("loqi-search-input");
    input?.focus();
    input?.select();
}

function closeLoqiModal() {
    document.getElementById("loqi-modal")?.classList.add("hidden");
    document.getElementById("loqi-button")?.focus();
}

function renderLoqiModal() {
    const title = document.getElementById("loqi-modal-title");
    const textBox = document.getElementById("loqi-text");
    if (!title || !textBox) return;
    title.textContent = `LOQI (${lastReasonerLoqiSource})`;
    const lines = (lastReasonerLoqi || "").split("\n").map((line) => line.replace(/\r$/, ""));
    const declarations = indexLoqiDeclarations(lines);
    let insideObject = false;
    textBox.innerHTML = lines.map((line, index) => {
        let html;
        if (LOQI_OBJECT_HEADER_RE.test(line)) {
            html = renderLoqiObjectHeader(line, declarations);
            insideObject = !/}\s*(\[.*\])?\s*$/.test(line);
        } else if (insideObject && LOQI_RELATIONSHIP_RE.test(line)) {
            html = renderLoqiRelationship(line, declarations);
        } else {
            html = escapeHtml(line);
            if (/^\s*}/.test(line)) insideObject = false;
        }
        return `<div class="loqi-line"><span class="loqi-line-number">${index + 1}</span>` +
            `<span class="loqi-line-text">${html || " "}</span></div>`;
    }).join("");
    textBox.scrollTop = 0;
    loqiJumpHistory = [];
    updateLoqiBackButton();
    updateLoqiSearch();
}

// Заголовок объекта (objDecl/varDecl): [var v =] obj name : Type {
const LOQI_OBJECT_HEADER_RE =
    /^([ \t]*(?:var[ \t]+[A-Za-z0-9_]+[ \t]*=[ \t]*)?obj[ \t]+[A-Za-z0-9_]+[ \t]*:[ \t]*)([A-Za-z0-9_]+)(.*)$/;
// Связь внутри тела объекта, как её пишет LoqiRenderer: rel(target1, target2) [ meta ];
const LOQI_RELATIONSHIP_RE = /^([ \t]+[A-Za-z0-9_]+[ \t]*\()([^()]*)(\).*)$/;
const LOQI_DECLARATION_NAMES_RE =
    /^[ \t]*(?:(?:class|enum)[ \t]+([A-Za-z0-9_]+)|(?:var[ \t]+([A-Za-z0-9_]+)[ \t]*=[ \t]*)?obj[ \t]+([A-Za-z0-9_]+)[ \t]*:)/;
var loqiJumpHistory = [];

// Имя объявления (class, enum, obj, var) → индекс строки заголовка.
function indexLoqiDeclarations(lines) {
    const declarations = new Map();
    lines.forEach((line, index) => {
        const match = LOQI_DECLARATION_NAMES_RE.exec(line);
        if (!match) return;
        for (const name of match.slice(1)) {
            if (name && !declarations.has(name)) declarations.set(name, index);
        }
    });
    return declarations;
}

function renderLoqiReference(name, declarations) {
    const line = declarations.get(name);
    if (line === undefined) {
        return `<span class="loqi-ref-missing" title="Not declared in this LOQI">${escapeHtml(name)}</span>`;
    }
    return `<a href="#" class="loqi-ref" data-line="${line}" title="Go to ${escapeHtml(name)} (line ${line + 1})">` +
        `${escapeHtml(name)}</a>`;
}

function renderLoqiObjectHeader(line, declarations) {
    const [, head, typeName, tail] = LOQI_OBJECT_HEADER_RE.exec(line);
    // Классы обычно объявлены в domain.loqi, а не в этом тексте: ссылка только если класс здесь есть.
    const type = declarations.has(typeName) ? renderLoqiReference(typeName, declarations) : escapeHtml(typeName);
    return escapeHtml(head) + type + escapeHtml(tail);
}

function renderLoqiRelationship(line, declarations) {
    const [, head, targets, tail] = LOQI_RELATIONSHIP_RE.exec(line);
    const targetsHtml = targets.replace(/[A-Za-z0-9_]+|[^A-Za-z0-9_]+/g, (part) =>
        /^[A-Za-z0-9_]+$/.test(part) ? renderLoqiReference(part, declarations) : escapeHtml(part)
    );
    return escapeHtml(head) + targetsHtml + escapeHtml(tail);
}

function scrollLoqiToLine(line) {
    const textBox = document.getElementById("loqi-text");
    const lineElement = textBox?.children[line];
    if (!textBox || !lineElement) return;
    textBox.scrollTop = lineElement.offsetTop - 8;
}

function jumpToLoqiLine(line) {
    const textBox = document.getElementById("loqi-text");
    const lineElement = textBox?.children[line];
    if (!textBox || !lineElement) return;
    loqiJumpHistory.push(textBox.scrollTop);
    updateLoqiBackButton();
    scrollLoqiToLine(line);
    textBox.querySelectorAll(".loqi-line-target").forEach((element) => element.classList.remove("loqi-line-target"));
    // Перезапуск анимации, если переходим на ту же строку повторно.
    void lineElement.offsetWidth;
    lineElement.classList.add("loqi-line-target");
}

function loqiJumpBack() {
    const textBox = document.getElementById("loqi-text");
    if (!textBox || loqiJumpHistory.length === 0) return;
    textBox.scrollTop = loqiJumpHistory.pop();
    updateLoqiBackButton();
}

function updateLoqiBackButton() {
    const button = document.getElementById("loqi-back-button");
    if (button) button.disabled = loqiJumpHistory.length === 0;
}

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Заголовки верхнеуровневых объявлений LOQI (правила classDecl, enumDecl, objDecl, varDecl):
//   class Name [: Parent] {    enum Name {    obj name : Type {    var v = obj name : Type {
// Имя подходит, если содержит запрос как подстроку (без учёта регистра).
// Члены класса `obj prop x: T` / `obj rel r(...)` не совпадают: после имени нет двоеточия.
function buildLoqiDeclarationRegex(query) {
    const name = `${LOQI_IDENTIFIER_CHAR}*${escapeRegExp(query)}${LOQI_IDENTIFIER_CHAR}*`;
    const identifier = `${LOQI_IDENTIFIER_CHAR}+`;
    const space = "[ \\t]";
    return new RegExp(
        `^${space}*(?:` +
            `(class|enum)${space}+(${name})(?!${LOQI_IDENTIFIER_CHAR})` +
            `|(?:var${space}+${identifier}${space}*=${space}*)?(obj)${space}+(${name})${space}*:` +
            `|(var)${space}+(${name})${space}*=${space}*obj${space}+${identifier}${space}*:` +
        ")",
        "gim",
    );
}

function findLoqiDeclarations(text, query) {
    const lineStarts = [0];
    for (let index = text.indexOf("\n"); index !== -1; index = text.indexOf("\n", index + 1)) {
        lineStarts.push(index + 1);
    }
    const lineOf = (offset) => {
        let low = 0;
        let high = lineStarts.length - 1;
        while (low < high) {
            const middle = (low + high + 1) >> 1;
            if (lineStarts[middle] <= offset) low = middle; else high = middle - 1;
        }
        return low;
    };

    const matches = [];
    for (const match of text.matchAll(buildLoqiDeclarationRegex(query))) {
        const kind = match[1] || match[3] || match[5];
        const name = match[2] || match[4] || match[6];
        matches.push({line: lineOf(match.index), kind: kind.toLowerCase(), name});
    }
    return matches;
}

function updateLoqiSearch() {
    const query = document.getElementById("loqi-search-input")?.value.trim() || "";
    loqiMatches = query && lastReasonerLoqi ? findLoqiDeclarations(lastReasonerLoqi, query) : [];
    loqiMatchIndex = loqiMatches.length > 0 ? 0 : -1;
    showLoqiMatch(query);
}

function stepLoqiMatch(delta) {
    if (loqiMatches.length === 0) return;
    loqiMatchIndex = (loqiMatchIndex + delta + loqiMatches.length) % loqiMatches.length;
    showLoqiMatch(document.getElementById("loqi-search-input")?.value.trim() || "");
}

function showLoqiMatch(query) {
    const textBox = document.getElementById("loqi-text");
    const status = document.getElementById("loqi-search-status");
    if (!textBox || !status) return;

    textBox.querySelectorAll(".loqi-line-match, .loqi-line-current").forEach((line) => {
        line.classList.remove("loqi-line-match", "loqi-line-current");
    });
    status.title = "";
    if (!query) {
        status.textContent = "";
        return;
    }
    if (loqiMatches.length === 0) {
        status.textContent = "No declarations";
        return;
    }

    const lines = textBox.children;
    loqiMatches.forEach((match) => lines[match.line]?.classList.add("loqi-line-match"));
    const current = loqiMatches[loqiMatchIndex];
    const currentLine = lines[current.line];
    currentLine?.classList.add("loqi-line-current");
    status.textContent = `${loqiMatchIndex + 1}/${loqiMatches.length} · ${current.kind} ${current.name}`;
    status.title = status.textContent;
    scrollLoqiToLine(current.line);
}

async function copyLoqiText() {
    try {
        await navigator.clipboard.writeText(lastReasonerLoqi || "");
    } catch (error) {
        alert(`Could not copy LOQI: ${error}`);
    }
}

function initializeLoqiModal() {
    const modal = document.getElementById("loqi-modal");
    const form = document.getElementById("loqi-search-form");
    const input = document.getElementById("loqi-search-input");
    if (!modal || !form || !input) return;

    input.addEventListener("input", updateLoqiSearch);
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        stepLoqiMatch(1);
    });
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && event.shiftKey) {
            event.preventDefault();
            stepLoqiMatch(-1);
        }
    });
    modal.addEventListener("click", (event) => {
        if (event.target === modal) closeLoqiModal();
    });
    document.getElementById("loqi-text")?.addEventListener("click", (event) => {
        const reference = event.target.closest(".loqi-ref");
        if (!reference) return;
        event.preventDefault();
        jumpToLoqiLine(Number(reference.dataset.line));
    });
    document.addEventListener("keydown", (event) => {
        if (!isLoqiModalOpen()) return;
        if (event.key === "Escape") {
            closeLoqiModal();
        } else if (event.key === "ArrowLeft" && event.altKey) {
            event.preventDefault();
            loqiJumpBack();
        }
    });
}

initializeLoqiModal();
updateTraceView();
