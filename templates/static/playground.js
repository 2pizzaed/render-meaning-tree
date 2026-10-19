// --- Render Form State ---
const RENDER_CODE_STORAGE_KEY = "playground.render.code";
const RENDER_LANGUAGE_STORAGE_KEY = "playground.render.language";
const RENDER_TARGET_LANGUAGE_STORAGE_KEY = "playground.render.targetLanguage";
const RENDER_SEED_STORAGE_KEY = "playground.render.seed";
const ACTIVE_TAB_STORAGE_KEY = "playground.activeTabIndex";
const renderForm = document.querySelector('form[action="/"]');
const renderCodeTextarea = renderForm?.querySelector('textarea[name="code"]');
const renderLanguageSelect = renderForm?.querySelector('select[name="language"]');
const renderTargetLanguageSelect = renderForm?.querySelector('select[name="target_language"]');
const renderSeedInput = renderForm?.querySelector('input[name="seed"]');

function readStoredValue(key) {
    try {
        return localStorage.getItem(key);
    } catch (error) {
        console.warn(`Unable to read ${key} from localStorage:`, error);
        return null;
    }
}

function storeValue(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (error) {
        console.warn(`Unable to save ${key} to localStorage:`, error);
    }
}

function restoreSelectValue(selectElement, storageKey) {
    const savedValue = readStoredValue(storageKey);
    if (
        selectElement &&
        savedValue !== null &&
        Array.from(selectElement.options).some((option) => option.value === savedValue)
    ) {
        selectElement.value = savedValue;
    }
}

const savedRenderCode = readStoredValue(RENDER_CODE_STORAGE_KEY);
if (renderCodeTextarea && savedRenderCode !== null && renderCodeTextarea.value === "") {
    renderCodeTextarea.value = savedRenderCode;
}

restoreSelectValue(renderLanguageSelect, RENDER_LANGUAGE_STORAGE_KEY);
restoreSelectValue(renderTargetLanguageSelect, RENDER_TARGET_LANGUAGE_STORAGE_KEY);

// --- Code Editor ---
// Подсветка синтаксиса поля Code. Textarea остаётся источником кода для остального JS:
// редактор записывает в неё каждое изменение. Без CodeMirror (CDN недоступен) работает
// обычная textarea.
const CODE_EDITOR_MODES = {java: "text/x-java", python: "python", "c++": "text/x-c++src"};
const codeEditor = renderCodeTextarea && window.CodeMirror
    ? CodeMirror.fromTextArea(renderCodeTextarea, {
        mode: CODE_EDITOR_MODES[renderLanguageSelect?.value],
        lineNumbers: true,
        indentUnit: 4,
        extraKeys: {
            // Tab вставляет пробелы, а не символ табуляции: важно для отступов Python.
            Tab: (editor) => editor.execCommand(editor.somethingSelected() ? "indentMore" : "insertSoftTab"),
        },
    })
    : null;

if (codeEditor) {
    codeEditor.on("change", () => codeEditor.save());
    // Высота меняется перетаскиванием угла (resize: vertical): редактору нужна перерисовка.
    new ResizeObserver(() => codeEditor.refresh()).observe(codeEditor.getWrapperElement());
}

function setRenderCode(code) {
    if (codeEditor) {
        codeEditor.setValue(code);
    } else if (renderCodeTextarea) {
        renderCodeTextarea.value = code;
    }
}

function updateCodeEditorMode() {
    codeEditor?.setOption("mode", CODE_EDITOR_MODES[renderLanguageSelect?.value]);
}

const savedRenderSeed = readStoredValue(RENDER_SEED_STORAGE_KEY);
if (renderSeedInput && savedRenderSeed !== null && renderSeedInput.value === "") {
    renderSeedInput.value = savedRenderSeed;
}

if (renderForm && renderCodeTextarea) {
    renderForm.addEventListener("submit", () => {
        storeValue(RENDER_CODE_STORAGE_KEY, renderCodeTextarea.value);
        if (renderLanguageSelect) {
            storeValue(RENDER_LANGUAGE_STORAGE_KEY, renderLanguageSelect.value);
        }
        if (renderTargetLanguageSelect) {
            storeValue(RENDER_TARGET_LANGUAGE_STORAGE_KEY, renderTargetLanguageSelect.value);
        }
        if (renderSeedInput) {
            storeValue(RENDER_SEED_STORAGE_KEY, renderSeedInput.value);
        }
    });
}

if (renderLanguageSelect) {
    renderLanguageSelect.addEventListener("change", () => {
        updateCodeEditorMode();
        storeValue(RENDER_LANGUAGE_STORAGE_KEY, renderLanguageSelect.value);
    });
}

if (renderTargetLanguageSelect) {
    renderTargetLanguageSelect.addEventListener("change", () => {
        storeValue(RENDER_TARGET_LANGUAGE_STORAGE_KEY, renderTargetLanguageSelect.value);
    });
}

if (renderSeedInput) {
    renderSeedInput.addEventListener("input", () => {
        storeValue(RENDER_SEED_STORAGE_KEY, renderSeedInput.value);
    });
}

async function clearSituationCache() {
    const button = document.getElementById("clear-cache-button");
    if (!button) return;
    button.disabled = true;
    try {
        const response = await fetch("/clear-cache", {method: "POST"});
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        button.classList.add("done");
        setTimeout(() => button.classList.remove("done"), 1500);
    } catch (error) {
        alert(`Unable to clear cache: ${error}`);
    } finally {
        button.disabled = false;
    }
}

// --- Code Examples ---
const snippetInput = renderForm?.querySelector('input[name="snippet"]');
const snippetStatus = document.getElementById("snippet-status");
let loadedSnippetPath = snippetInput?.value || "";

function isKnownSnippet(path) {
    return Array.from(snippetInput?.list?.options || []).some((option) => option.value === path);
}

async function loadSnippet(path) {
    if (!renderCodeTextarea || !renderLanguageSelect) return;
    snippetStatus.textContent = "Loading...";
    snippetStatus.classList.remove("error");
    try {
        const response = await fetch(`/snippet?path=${encodeURIComponent(path)}`);
        const payload = await response.json();
        if (!payload.ok) {
            throw new Error(payload.error || `HTTP ${response.status}`);
        }
        renderLanguageSelect.value = payload.language;
        updateCodeEditorMode();
        setRenderCode(payload.code);
        storeValue(RENDER_CODE_STORAGE_KEY, payload.code);
        storeValue(RENDER_LANGUAGE_STORAGE_KEY, payload.language);
        loadedSnippetPath = path;
        snippetStatus.textContent = "";
    } catch (error) {
        snippetStatus.textContent = `Could not load example: ${error.message || error}`;
        snippetStatus.classList.add("error");
    }
}

if (snippetInput && snippetStatus) {
    // Выбор из списка (или точный ввод пути) сразу загружает файл.
    snippetInput.addEventListener("input", () => {
        const path = snippetInput.value;
        if (path !== loadedSnippetPath && isKnownSnippet(path)) {
            loadSnippet(path);
        }
    });
    snippetInput.addEventListener("keydown", (event) => {
        // Enter не отправляет форму: он только подтверждает выбор примера.
        if (event.key !== "Enter") return;
        event.preventDefault();
        if (isKnownSnippet(snippetInput.value)) {
            loadSnippet(snippetInput.value);
        }
    });
}

// --- Tabs Logic ---
function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
        tabcontent[i].classList.remove("active");
    }
    tablinks = document.getElementsByClassName("tab");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove("active");
    }
    document.getElementById(tabName).style.display = "block";
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");

    const activeTabIndex = Array.prototype.indexOf.call(tablinks, evt.currentTarget);
    if (activeTabIndex >= 0) {
        storeValue(ACTIVE_TAB_STORAGE_KEY, String(activeTabIndex));
    }
}

function restoreActiveTab() {
    const savedTabIndex = Number.parseInt(readStoredValue(ACTIVE_TAB_STORAGE_KEY), 10);
    const tablinks = document.getElementsByClassName("tab");
    const tabButton = Number.isInteger(savedTabIndex) ? tablinks[savedTabIndex] : null;
    const tabName = tabButton?.dataset.tabName;
    if (tabButton && tabName && document.getElementById(tabName)) {
        openTab({currentTarget: tabButton}, tabName);
    }
}

restoreActiveTab();

// --- Source Map Viewer ---
let sourceMapEditor = null;

function initializeSourceMapEditor() {
    const container = document.getElementById("source-map-editor");
    if (!container || typeof JSONEditor !== "function" || typeof SOURCE_MAP_DATA === "undefined") {
        return;
    }

    sourceMapEditor = new JSONEditor(container, {
        mode: "view",
        modes: ["view"],
        search: true,
        mainMenuBar: true,
        navigationBar: true,
        statusBar: false,
        enableSort: false,
        enableTransform: false,
    });
    sourceMapEditor.set(SOURCE_MAP_DATA);
}

initializeSourceMapEditor();

function findSourceMapNodePath(value, nodeId, nodeType = null, path = ["origin"]) {
    if (!value || typeof value !== "object") {
        return null;
    }

    if (
        !Array.isArray(value) &&
        Object.prototype.hasOwnProperty.call(value, "id") &&
        Object.prototype.hasOwnProperty.call(value, "type") &&
        String(value.id) === String(nodeId) &&
        (nodeType === null || value.type === nodeType)
    ) {
        return path;
    }

    const keys = Array.isArray(value) ? value.map((_, index) => index) : Object.keys(value);
    for (const key of keys) {
        const childPath = findSourceMapNodePath(value[key], nodeId, nodeType, [...path, key]);
        if (childPath) {
            return childPath;
        }
    }

    return null;
}

function navigateToSourceMapNode(nodeId, nodeType = null) {
    const origin = SOURCE_MAP_DATA?.origin;
    if (!sourceMapEditor || !origin) {
        return false;
    }

    const path = findSourceMapNodePath(origin, nodeId, nodeType);
    if (!path) {
        const typeSuffix = nodeType === null ? "" : ` (${nodeType})`;
        console.warn(`Source map node not found: #${nodeId}${typeSuffix}`);
        return false;
    }

    const sourceMapTabButton = document.querySelector("button[data-tab-name='tab-source-map']");
    if (sourceMapTabButton) {
        openTab({currentTarget: sourceMapTabButton}, "tab-source-map");
    }

    sourceMapEditor.expand({path, isExpand: true, recursive: false, withPath: true});
    sourceMapEditor.setSelection({path});

    requestAnimationFrame(() => {
        const selectedRow = document.querySelector(
            "#source-map-editor tr.jsoneditor-selected.jsoneditor-first",
        );
        selectedRow?.scrollIntoView({behavior: "smooth", block: "center"});
    });

    return true;
}

function initializeNodeIdSearch() {
    const form = document.getElementById("node-id-search-form");
    const input = document.getElementById("node-id-search-input");
    if (!form || !input) {
        return;
    }

    input.addEventListener("input", () => input.setCustomValidity(""));
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const nodeId = input.value.trim();
        if (!nodeId) {
            input.setCustomValidity("Enter a node ID.");
            input.reportValidity();
            return;
        }

        input.setCustomValidity("");
        if (!navigateToSourceMapNode(nodeId)) {
            input.setCustomValidity(`Node #${nodeId} was not found in Source Map.`);
            input.reportValidity();
        }
    });
}

initializeNodeIdSearch();

// --- Inspector Logic ---
function handleTokenClick(element) {
    const nodeId = element.getAttribute("data-node-id");
    const tokenIndex = element.getAttribute("data-token-index");
    const container = document.getElementById("node-info-content");

    document.querySelectorAll(".token").forEach((token) => {
        token.classList.remove("selected-token");
    });
    element.classList.add("selected-token");

    document.getElementById("selected-token-info").textContent =
        `"${element.innerText}" (Index: ${tokenIndex})`;

    const inspectorTabBtn = document.querySelector("button[onclick*='tab-inspector']");
    if (!inspectorTabBtn.classList.contains("active")) {
        openTab({currentTarget: inspectorTabBtn}, "tab-inspector");
    }

    if (!nodeId || !AST_DATA[nodeId]) {
        container.innerHTML = '<span style="color: #999;">Node info not available.</span>';
        return;
    }

    let currentId = nodeId;
    let path = [];
    while (currentId && AST_DATA[currentId]) {
        path.push(AST_DATA[currentId]);
        currentId = AST_DATA[currentId].parent_id;
    }

    let html = "";
    const hierarchyNodes = path.reverse();
    hierarchyNodes.forEach((node, index) => {
        const indent = index * 15;
        let badges = `<span class="badge" title="Node ID">#${node.id}</span>`;

        if (node.token_range) {
            badges += `<span class="badge range-badge" title="Token Range indices">Tokens: ${node.token_range[0]} - ${node.token_range[1]}</span>`;
        }

        if (node.collection_id !== null) {
            const prefix = isNaN(node.collection_id) ? "Key" : "Idx";
            badges += `<span class="badge collection-badge">${prefix}: ${node.collection_id}</span>`;
        }

        const fieldStr = node.field
            ? `<span style="color:#666; margin-right:5px; font-weight:bold;">.${node.field}</span>`
            : "";

        html += `
            <div class="node-item" style="margin-left: ${indent}px" role="button" tabindex="0"
                 title="Show this node in Source Map">
                <div class="main-info">
                    ${fieldStr}
                    <span class="type">${node.type}</span>
                </div>
                <div class="meta">
                    ${badges}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    container.querySelectorAll(".node-item").forEach((item, index) => {
        const node = hierarchyNodes[index];
        const navigate = () => navigateToSourceMapNode(node.id, node.type);
        item.addEventListener("click", navigate);
        item.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                navigate();
            }
        });
    });
}

// --- Export ---
const exportSituationTag = document.getElementById("export_situation");
// Параметры отрисованной ситуации: экспорт не зависит от правок формы после Render.
const EXPORT_SITUATION = exportSituationTag ? JSON.parse(exportSituationTag.textContent) : null;
// Вкладка успевает загрузить документ, а браузер — начать скачивание; ссылку освобождаем позже.
const EXPORT_URL_LIFETIME_MS = 60000;

function jsonBlob(data) {
    // Blob с типом application/json браузер показывает как сырой текст в новой вкладке.
    return new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
}

// tab — вкладка, открытая заранее по клику: после await браузер блокирует window.open.
function deliverBlob(blob, filename, mode, tab = null) {
    const url = URL.createObjectURL(blob);
    if (mode === "download") {
        // Ссылку вне документа часть браузеров открывает без имени из download (UUID без расширения).
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.hidden = true;
        document.body.append(link);
        link.click();
        link.remove();
    } else if (tab) {
        tab.location.href = url;
    } else if (!window.open(url, "_blank")) {
        showExportError("Could not open a new tab: the browser blocked the popup.");
    }
    setTimeout(() => URL.revokeObjectURL(url), EXPORT_URL_LIFETIME_MS);
}

function exportJson(filename, data, mode) {
    deliverBlob(jsonBlob(data), filename, mode);
}

function showExportError(message) {
    document.getElementById("export-error-text").textContent = message;
    document.getElementById("export-error-dialog").showModal();
}

function setExportStatus(done, total, text) {
    const status = document.getElementById("export-status");
    const progress = document.getElementById("export-progress");
    status.hidden = false;
    progress.max = total;
    progress.value = done;
    document.getElementById("export-status-text").textContent = text;
}

// Несколько вопросов упаковываются в ZIP, а его можно только скачать.
function updateExportQuestionButtons(busy = false) {
    const input = document.getElementById("export-question-count");
    const openButton = document.getElementById("export-questions-open");
    const downloadButton = document.getElementById("export-questions-download");
    if (!input || !openButton || !downloadButton) return;
    const zipped = Number(input.value) > 1;
    input.disabled = busy;
    downloadButton.disabled = busy;
    openButton.disabled = busy || zipped;
    openButton.title = zipped ? "Several questions are packed into a ZIP archive: download it" : "";
}

async function fetchExportQuestion(index) {
    const response = await fetch("/export-question", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            code: EXPORT_SITUATION.code,
            language: EXPORT_SITUATION.language,
            target_language: EXPORT_SITUATION.target_language,
            seed: EXPORT_SITUATION.seed,
            index,
        }),
    });
    return response.json().catch(() => ({ok: false, error: `HTTP ${response.status}`}));
}

async function exportQuestions(mode) {
    const input = document.getElementById("export-question-count");
    if (!EXPORT_SITUATION || !input?.reportValidity()) return;
    const count = Number(input.value);
    if (count > 1 && typeof JSZip !== "function") {
        showExportError("JSZip is not loaded: the ZIP archive cannot be built.");
        return;
    }
    const tab = mode === "open" ? window.open("", "_blank") : null;
    if (mode === "open" && !tab) {
        showExportError("Could not open a new tab: the browser blocked the popup.");
        return;
    }

    updateExportQuestionButtons(true);
    const questions = [];
    // Задачу, которую нельзя упаковать, сервер пропускает (warning в логе playground).
    const skipped = [];
    try {
        for (let index = 0; index < count; index++) {
            setExportStatus(index, count, `Packing question ${index + 1} of ${count}...`);
            const payload = await fetchExportQuestion(index);
            if (payload.ok) {
                questions.push(payload);
            } else if (payload.skipped) {
                skipped.push(`#${index + 1}: ${payload.error}`);
            } else {
                throw new Error(payload.error);
            }
        }
        if (questions.length === 0) {
            throw new Error(`No question could be packed:\n${skipped.join("\n")}`);
        }

        if (questions.length === 1) {
            const [{name, question}] = questions;
            deliverBlob(jsonBlob(question), `${name}.json`, mode, tab);
        } else {
            setExportStatus(count, count, "Building ZIP archive...");
            const zip = new JSZip();
            questions.forEach(({name, question}) => zip.file(`${name}.json`, JSON.stringify(question, null, 2)));
            const archive = await zip.generateAsync({type: "blob", mimeType: "application/zip"});
            deliverBlob(archive, `questions-seed-${EXPORT_SITUATION.seed}.zip`, "download");
        }
        const skippedText = skipped.length ? `, ${skipped.length} skipped (see the playground log)` : "";
        setExportStatus(count, count, `Exported ${questions.length} of ${count}${skippedText}.`);
    } catch (error) {
        tab?.close();
        setExportStatus(0, count, "Export failed.");
        showExportError(String(error.message || error));
    } finally {
        updateExportQuestionButtons();
    }
}

document.getElementById("export-question-count")?.addEventListener("input", () => updateExportQuestionButtons());
updateExportQuestionButtons();

// Контракт выбора ответа общий с CompPrehension (docs/ideas/function_return_dropdown.md):
// выбор - событие ANSWER_EVENT на элементе ответа, клик по умолчанию отправляет его,
// а клик элемента с data-comp-ph-custom-click обрабатывает код фрагмента.
const ANSWER_EVENT = "compph:on-answer-evaluated";
const ANSWER_ID_PATTERN = /^answer_(\d+)$/;

function answerElementOf(target) {
    for (let element = target; element instanceof Element; element = element.parentElement) {
        if (ANSWER_ID_PATTERN.test(element.id)) return element;
    }
    return null;
}

document.addEventListener("click", (event) => {
    const answer = answerElementOf(event.target);
    if (!answer || answer.disabled || answer.hasAttribute("data-comp-ph-custom-click")) return;
    answer.dispatchEvent(new CustomEvent(ANSWER_EVENT, { bubbles: true }));
});

document.addEventListener(ANSWER_EVENT, (event) => {
    const answer = answerElementOf(event.target);
    if (answer) handleAnswer(answer);
});

function handleAnswer(btn) {
    const actionId = btn.id.match(ANSWER_ID_PATTERN)[1];
    const astId = btn.getAttribute("data-node-id");
    const astNodeType = btn.getAttribute("data-node-type");
    const scriptTag = document.getElementById("answer_objects");
    let ansData = {};
    try {
        if (scriptTag && scriptTag.textContent.trim()) {
            ansData = JSON.parse(scriptTag.textContent);
        }
    } catch (error) {
        console.error("Error parsing answer_objects:", error);
    }

    if (typeof ansData[actionId] === "string" && ansData[actionId]) {
        appendTraceAction(ansData[actionId]);
        renderReasoningResult(null);
    } else {
        console.warn(`No domain info found for action_id: ${actionId}`);
        alert(`AST Node Id: ${astId}\nAST Type: ${astNodeType}\nAction id (buttons before): ${actionId}`);
    }
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    }[char]));
}
