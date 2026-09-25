// Tests the chat's markdown renderer without needing Odoo: the functions are extracted from the
// source and evaluated with `markup` replaced by the identity. Run: node --test "tests/js/*.test.mjs"
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(
    new URL("../../odoo_addon/ai_assistant_chat/static/src/chat/ai_chat.js", import.meta.url), "utf8");
const body = src.slice(src.indexOf("function escapeHtml"), src.indexOf("export class AiChat"))
    .replaceAll("export function", "function");
const { renderMarkdown: render, groupSources } = new Function(
    "markup", `${body}; return { renderMarkdown, groupSources };`)((s) => s);

test("escapes HTML before formatting (XSS)", () => {
    const out = render('<script>alert(1)</script><img src=x onerror=alert(1)>');
    assert.ok(!out.includes("<script"), out);
    assert.ok(!out.includes("<img"), out);
    assert.match(out, /&lt;script&gt;/);
});

test("formatting cannot reintroduce HTML", () => {
    const out = render('**<b onclick="x()">hello</b>** and `<i>`');
    assert.ok(!/<b onclick/.test(out), out);
    assert.ok(!/<i>/.test(out.replace(/<\/?(strong|em|code|p|ul|ol|li)>/g, "")), out);
});

test("quotes inside attributes cannot break out", () => {
    assert.ok(!render('" onmouseover="alert(1)').includes('"'));
});

test("bold, italics and inline code", () => {
    assert.equal(render("**8.54** days and *today* `x`"),
        "<p><strong>8.54</strong> days and <em>today</em> <code>x</code></p>");
});

test("bullet and numbered lists", () => {
    assert.equal(render("* one\n* two"), "<ul><li>one</li><li>two</li></ul>");
    assert.equal(render("1. a\n2. b"), "<ol><li>a</li><li>b</li></ol>");
});

test("a paragraph after a list closes the list", () => {
    assert.equal(render("- a\ntext"), "<ul><li>a</li></ul><p>text</p>");
});

test("asterisks used as multiplication are left alone", () => {
    assert.ok(render("2 * 3 = 6").includes("2 * 3 = 6"));
});

test("groupSources: one badge per file with its sections in the title", () => {
    const g = groupSources([
        { source: "hr/a.md", section: "S1" }, { source: "hr/a.md", section: "S2" },
        { source: "hr/b.md", section: "" }]);
    assert.deepEqual(g, [{ source: "a.md", title: "S1\nS2" }, { source: "b.md", title: "" }]);
    assert.deepEqual(groupSources(undefined), []);
});
