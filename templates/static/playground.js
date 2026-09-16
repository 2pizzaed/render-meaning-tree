// --- Render Form State ---
const RENDER_CODE_STORAGE_KEY = "playground.render.code";
const RENDER_LANGUAGE_STORAGE_KEY = "playground.render.language";
const RENDER_TARGET_LANGUAGE_STORAGE_KEY = "playground.render.targetLanguage";
const ACTIVE_TAB_STORAGE_KEY = "playground.activeTabIndex";
const renderForm = document.querySelector('form[action="/"]');
const renderCodeTextarea = renderForm?.querySelector('textarea[name="code"]');
const renderLanguageSelect = renderForm?.querySelector('select[name="language"]');
const renderTargetLanguageSelect = renderForm?.querySelector('select[name="target_language"]');

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

if (renderForm && renderCodeTextarea) {
    renderForm.addEventListener("submit", () => {
        storeValue(RENDER_CODE_STORAGE_KEY, renderCodeTextarea.value);
        if (renderLanguageSelect) {
            storeValue(RENDER_LANGUAGE_STORAGE_KEY, renderLanguageSelect.value);
        }
        if (renderTargetLanguageSelect) {
            storeValue(RENDER_TARGET_LANGUAGE_STORAGE_KEY, renderTargetLanguageSelect.value);
        }
    });
}

if (renderLanguageSelect) {
    renderLanguageSelect.addEventListener("change", () => {
        storeValue(RENDER_LANGUAGE_STORAGE_KEY, renderLanguageSelect.value);
    });
}

if (renderTargetLanguageSelect) {
    renderTargetLanguageSelect.addEventListener("change", () => {
        storeValue(RENDER_TARGET_LANGUAGE_STORAGE_KEY, renderTargetLanguageSelect.value);
    });
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
        renderCodeTextarea.value = payload.code;
        renderLanguageSelect.value = payload.language;
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

function openSourceMapJson() {
    if (typeof SOURCE_MAP_DATA === "undefined" || SOURCE_MAP_DATA === null) {
        return;
    }
    // Blob с типом application/json браузер показывает как сырой текст в новой вкладке.
    const blob = new Blob([JSON.stringify(SOURCE_MAP_DATA, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const tab = window.open(url, "_blank");
    if (!tab) {
        alert("Could not open a new tab: the browser blocked the popup.");
    }
    // Вкладка успевает загрузить документ; ссылку освобождаем позже.
    setTimeout(() => URL.revokeObjectURL(url), 60000);
}

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

function handleButtonClick(btn) {
    const actionId = btn.getAttribute("data-action-id");
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
