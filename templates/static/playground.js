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
    path.reverse().forEach((node, index) => {
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
            <div class="node-item" style="margin-left: ${indent}px">
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
        traceData.push(ansData[actionId]);
        updateTraceView();
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
