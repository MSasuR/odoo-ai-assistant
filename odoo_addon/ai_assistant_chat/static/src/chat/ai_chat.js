import { Component, markup, onPatched, useRef, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const SUGGESTIONS = [
    _t("How many vacation days do I have left?"),
    _t("How many leave requests did I have this year?"),
];

function escapeHtml(s) {
    return s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function inline(s) {
    return s
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}

/**
 * Minimal markdown (bold, italics, code, lists, line breaks).
 * Safe by construction: ALL HTML in the text is escaped before any formatting is applied,
 * so the output only contains the tags this function generates.
 */
export function renderMarkdown(text) {
    const out = [];
    let list = null; // "ul" | "ol" | null
    const closeList = () => {
        if (list) {
            out.push(`</${list}>`);
            list = null;
        }
    };
    for (const raw of escapeHtml(text).split("\n")) {
        const line = raw.trimEnd();
        const bullet = line.match(/^\s*[*-]\s+(.*)$/);
        const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
        if (bullet || numbered) {
            const kind = bullet ? "ul" : "ol";
            if (list !== kind) {
                closeList();
                out.push(`<${kind}>`);
                list = kind;
            }
            out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
        } else {
            closeList();
            out.push(line ? `<p>${inline(line)}</p>` : "");
        }
    }
    closeList();
    return markup(out.join(""));
}

/** One badge per file; the title lists the cited sections. */
export function groupSources(sources) {
    const bySource = new Map();
    for (const { source, section } of sources || []) {
        if (!bySource.has(source)) {
            bySource.set(source, new Set());
        }
        if (section) {
            bySource.get(source).add(section);
        }
    }
    return [...bySource].map(([source, sections]) => ({
        source: source.split("/").pop(),
        title: [...sections].join("\n"),
    }));
}

export class AiChat extends Component {
    static template = "ai_assistant_chat.AiChat";
    static props = [];

    setup() {
        this.suggestions = SUGGESTIONS;
        this.state = useState({
            open: false,
            loading: false,
            input: "",
            conversationId: null,
            messages: [], // {id, role: "user" | "assistant" | "error", text, html?, sources?}
        });
        this.listRef = useRef("list");
        this.inputRef = useRef("input");
        this.nextId = 1;
        onPatched(() => {
            const el = this.listRef.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }

    toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            setTimeout(() => this.inputRef.el && this.inputRef.el.focus(), 0);
        }
    }

    reset() {
        this.state.messages = [];
        this.state.conversationId = null;
        this.state.input = "";
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    useSuggestion(text) {
        this.state.input = text;
        this.send();
    }

    async send() {
        const text = this.state.input.trim();
        if (!text || this.state.loading) {
            return;
        }
        this.state.messages.push({ id: this.nextId++, role: "user", text });
        this.state.input = "";
        this.state.loading = true;
        try {
            const res = await rpc("/ai_assistant/chat", {
                message: text,
                conversation_id: this.state.conversationId,
            });
            if (res.error) {
                this.state.messages.push({ id: this.nextId++, role: "error", text: res.error });
            } else {
                this.state.conversationId = res.conversation_id;
                this.state.messages.push({
                    id: this.nextId++,
                    role: "assistant",
                    text: res.answer,
                    html: renderMarkdown(res.answer),
                    sources: groupSources(res.sources),
                });
            }
        } catch {
            this.state.messages.push({
                id: this.nextId++,
                role: "error",
                text: _t("The question could not be sent. Check your connection."),
            });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("systray").add("ai_assistant_chat.chat", { Component: AiChat }, { sequence: 5 });
