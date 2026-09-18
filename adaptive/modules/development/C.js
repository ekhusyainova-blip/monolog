// adaptive/modules/development/C.js — фрагмент: логирование и save/check
// Только события. Никаких if в бизнес-логике — только match.

window.MonologDevC = window.MonologDevC || {};

MonologDevC.log = function (node, text, kind) {
  const line = document.createElement("div");
  line.className = "dev-log-" + (kind || "info");
  const t = new Date().toISOString().substr(11, 8);
  line.textContent = "[" + t + "] " + text;
  node.prepend(line);
  const lines = node.querySelectorAll("div");
  for (let i = 40; i < lines.length; i++) lines[i].remove();
};

MonologDevC.report = function (node, label, res) {
  const ok = res && res.ok;
  const status = res ? res.status : "no-response";
  const body = res && res.data ? JSON.stringify(res.data).slice(0, 200) : "";
  MonologDevC.log(
    node,
    label + " → " + status + (ok ? " ok" : " FAIL") + " " + body,
    ok ? "ok" : "err"
  );
  MonologDevC.state(label, "C", !!ok, status + " " + body);
};

MonologDevC.onSave = async function (logNode, branch, path, content, sha) {
  MonologDevC.log(logNode, "save " + path, "info");
  const res = await MonologDevA.save(branch, path, content, sha);
  MonologDevC.report(logNode, "save", res);
};

MonologDevC.onCheck = async function (logNode, branch, path) {
  MonologDevC.log(logNode, "check " + path, "info");
  const res = await MonologDevA.check(branch, path);
  MonologDevC.report(logNode, "check", res);
};

MonologDevC.onRead = async function (logNode, branch, path) {
  const res = await MonologDevA.read(branch, path);
  MonologDevC.report(logNode, "read " + path, res);
  return res;
};