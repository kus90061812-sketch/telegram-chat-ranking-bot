from __future__ import annotations

import base64
import binascii
import logging
import secrets
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .storage import ChatGroup, ChatSettings, Storage


LOGGER = logging.getLogger(__name__)


class WebSettings(Protocol):
    admin_username: str
    admin_password: str
    port: int


CSS = """
:root{color-scheme:dark;--bg:#090b10;--panel:#11151d;--line:#252b38;--text:#f5f7fb;
--muted:#969fb0;--red:#ff3b4f;--red2:#b9102d;--green:#37d67a}*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at top,#1b1118 0,#090b10 38%);color:var(--text);
font-family:Arial,'Noto Sans KR',sans-serif;min-height:100vh}a{color:inherit;text-decoration:none}
.wrap{width:min(960px,calc(100% - 28px));margin:0 auto;padding:34px 0 70px}.brand{display:flex;
align-items:center;gap:12px;margin-bottom:28px}.logo{width:42px;height:42px;border-radius:13px;
background:linear-gradient(145deg,var(--red),var(--red2));display:grid;place-items:center;font-size:22px;
box-shadow:0 10px 30px #ff304333}.brand h1{font-size:21px;margin:0}.brand p{margin:3px 0 0;
font-size:13px;color:var(--muted)}.card{background:#11151de8;border:1px solid var(--line);border-radius:18px;
padding:22px;box-shadow:0 18px 55px #0007;margin-bottom:16px}.card h2{font-size:18px;margin:0 0 8px}
.muted{color:var(--muted);font-size:13px;line-height:1.55}.rooms{display:grid;gap:12px;margin-top:18px}
.room{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px;border:1px solid var(--line);
border-radius:14px;background:#0d1118;transition:.18s}.room:hover{border-color:#ff3b4f88;transform:translateY(-1px)}
.room strong{display:block;margin-bottom:5px}.room span{font-size:12px;color:var(--muted)}.arrow{color:var(--red);font-size:22px}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px}.back{color:var(--muted);font-size:14px}
.back:hover{color:#fff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}.field{margin-bottom:16px}
.field label{display:block;font-weight:700;font-size:13px;margin-bottom:8px}.field small{display:block;color:var(--muted);
font-size:12px;margin-top:6px}input,textarea{width:100%;border:1px solid var(--line);background:#0a0e14;color:#fff;
border-radius:11px;padding:12px 13px;font:inherit;outline:none;transition:.18s}input:focus,textarea:focus{border-color:var(--red);
box-shadow:0 0 0 3px #ff3b4f18}textarea{min-height:92px;resize:vertical}.prizes{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.section-title{font-size:15px;margin:6px 0 14px;padding-top:8px}.actions{position:sticky;bottom:14px;display:flex;
justify-content:flex-end;margin-top:22px}.save{border:0;border-radius:12px;background:linear-gradient(135deg,var(--red),var(--red2));
color:#fff;padding:13px 25px;font-weight:800;font-size:14px;cursor:pointer;box-shadow:0 12px 30px #ff30432d}.save:hover{filter:brightness(1.1)}
.notice{border:1px solid #37d67a55;background:#123321;color:#a5f4c5;padding:12px 14px;border-radius:11px;
font-size:13px;margin-bottom:16px}.error{border-color:#ff3b4f66;background:#35131a;color:#ffb8c0}.preview{white-space:pre-wrap;
line-height:1.65;background:#090c12;border:1px solid var(--line);border-radius:14px;padding:18px;font-size:14px}
.template{min-height:210px;font-family:Consolas,'Courier New',monospace;line-height:1.55}.template.small{min-height:100px}
.tokens{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 16px}.token{border:1px solid #384155;background:#171d28;
color:#cbd4e5;border-radius:999px;padding:6px 9px;font:12px Consolas,monospace;cursor:pointer}.token:hover{border-color:var(--red)}
.preview-title{font-size:13px;color:#ff9eaa;margin:18px 0 8px}.preview-title:first-child{margin-top:0}
@media(max-width:680px){.grid{grid-template-columns:1fr}.prizes{grid-template-columns:1fr 1fr}.card{padding:17px}.wrap{padding-top:22px}}
"""


def _valid_auth(header: str, settings: WebSettings) -> bool:
    try:
        scheme, encoded = header.split(" ", 1)
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        username = password = ""
        scheme = ""
    return (
        scheme.lower() == "basic"
        and secrets.compare_digest(username, settings.admin_username)
        and secrets.compare_digest(password, settings.admin_password)
    )


def _layout(content: str, subtitle: str = "채팅 순위 이벤트 관리") -> str:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>채팅 순위 관리자</title>
<style>{CSS}</style></head><body><main class="wrap"><div class="brand"><div class="logo">🏆</div>
<div><h1>채팅 순위 관리자</h1><p>{escape(subtitle)}</p></div></div>{content}</main></body></html>"""


def _chat_list(groups: list[ChatGroup]) -> str:
    if not groups:
        rooms = """<div class="notice error">등록된 소통방이 없습니다. 봇을 그룹에 추가한 뒤 그룹에서
<b>.도움말</b> 또는 아무 채팅을 한 번 보내주세요.</div>"""
    else:
        items = []
        for group in groups:
            items.append(
                f'<a class="room" href="/admin/chat/{group.chat_id}"><div><strong>{escape(group.title)}</strong>'
                f'<span>그룹 ID {group.chat_id}</span></div><div class="arrow">›</div></a>'
            )
        rooms = f'<div class="rooms">{"".join(items)}</div>'
    return _layout(
        f'<section class="card"><h2>소통방 선택</h2><p class="muted">수정할 방을 선택하세요. 저장 즉시 봇 답변에 반영됩니다.</p>{rooms}</section>'
    )


def _value(value: str) -> str:
    return escape(value, quote=True)


def _edit_form(group: ChatGroup, item: ChatSettings, saved: bool, error: str = "") -> str:
    notice = '<div class="notice">저장 완료! 다음 명령어부터 바로 반영됩니다.</div>' if saved else ""
    if error:
        notice = f'<div class="notice error">{escape(error)}</div>'
    content = f"""
<div class="topbar"><a class="back" href="/admin">← 소통방 목록</a><span class="muted">{escape(group.title)}</span></div>
{notice}<form method="post" action="/admin/chat/{group.chat_id}"><section class="card">
<h2>봇 표시 문구</h2><p class="muted">HTML 코드는 사용할 필요 없이 보이는 문구 그대로 입력하면 됩니다.</p>
<div class="field"><label for="event_title">이벤트 제목</label><input id="event_title" name="event_title" maxlength="255" required value="{_value(item.event_title)}"></div>
<div class="grid"><div class="field"><label for="daily_title">일간 순위 제목</label><input id="daily_title" name="daily_title" maxlength="255" required value="{_value(item.daily_title)}"></div>
<div class="field"><label for="weekly_title">주간 순위 제목</label><input id="weekly_title" name="weekly_title" maxlength="255" required value="{_value(item.weekly_title)}"></div></div>
<h3 class="section-title">주간 상금</h3><div class="prizes">
<div class="field"><label>1위</label><input name="prize_1" maxlength="100" value="{_value(item.prize_1)}"></div>
<div class="field"><label>2위</label><input name="prize_2" maxlength="100" value="{_value(item.prize_2)}"></div>
<div class="field"><label>3위</label><input name="prize_3" maxlength="100" value="{_value(item.prize_3)}"></div>
<div class="field"><label>4위</label><input name="prize_4" maxlength="100" value="{_value(item.prize_4)}"></div></div>
<div class="field"><label for="footer">순위 하단 안내문</label><textarea id="footer" name="footer" maxlength="1000">{_value(item.footer)}</textarea></div>
<div class="field"><label for="help_message">.도움말 추가 문구</label><textarea id="help_message" name="help_message" maxlength="2000">{_value(item.help_message)}</textarea></div>
<div class="field"><label for="top_limit">표시할 순위 인원</label><input id="top_limit" name="top_limit" type="number" min="3" max="50" value="{item.top_limit}"><small>3명부터 50명까지 설정할 수 있습니다.</small></div>
</section><section class="card"><h2>봇 답변 전체 편집</h2><p class="muted">글·이모지·줄바꿈·순서를 전부 수정할 수 있습니다. <b>{{치환값}}</b>은 실제 순위와 이름으로 자동 변경됩니다. 굵은 글씨는 <b>**글씨**</b>처럼 입력하세요. 아래 치환값 버튼을 누르면 현재 커서 위치에 들어갑니다.</p>
<div class="field"><label for="ranking_template">.채팅순위 전체 답변</label><div class="tokens" data-target="ranking_template">
<button type="button" class="token">{{EVENT_TITLE_BOLD}}</button><button type="button" class="token">{{DAILY_TITLE_BOLD}}</button><button type="button" class="token">{{DAY_DATE}}</button><button type="button" class="token">{{DAILY_RANKING}}</button><button type="button" class="token">{{WEEKLY_TITLE_BOLD}}</button><button type="button" class="token">{{WEEK_DATE}}</button><button type="button" class="token">{{PRIZE_LINE}}</button><button type="button" class="token">{{WEEKLY_RANKING}}</button><button type="button" class="token">{{FOOTER}}</button></div>
<textarea class="template" id="ranking_template" name="ranking_template" maxlength="6000" required>{_value(item.ranking_template)}</textarea></div>
<div class="grid"><div class="field"><label for="ranking_row_template">순위 한 줄 모양</label><div class="tokens" data-target="ranking_row_template"><button type="button" class="token">{{MEDAL}}</button><button type="button" class="token">{{POSITION}}</button><button type="button" class="token">{{NAME_BOLD}}</button><button type="button" class="token">{{COUNT}}</button></div><textarea class="template small" id="ranking_row_template" name="ranking_row_template" maxlength="500" required>{_value(item.ranking_row_template)}</textarea></div>
<div class="field"><label for="prize_line_template">상금표 모양</label><div class="tokens" data-target="prize_line_template"><button type="button" class="token">{{PRIZES}}</button></div><textarea class="template small" id="prize_line_template" name="prize_line_template" maxlength="500">{_value(item.prize_line_template)}</textarea><small>{{PRIZES}}에는 1~4위 상금이 한 줄에 하나씩 자동으로 표시됩니다.</small></div></div>
<div class="field"><label for="empty_ranking_message">집계된 채팅이 없을 때</label><input id="empty_ranking_message" name="empty_ranking_message" maxlength="500" required value="{_value(item.empty_ranking_message)}"></div>
<div class="field"><label for="personal_template">.나 전체 답변</label><div class="tokens" data-target="personal_template">
<button type="button" class="token">{{NAME_BOLD}}</button><button type="button" class="token">{{DAILY_COUNT}}</button><button type="button" class="token">{{DAILY_RANK}}</button><button type="button" class="token">{{DAILY_SUMMARY}}</button><button type="button" class="token">{{DAILY_GAP}}</button><button type="button" class="token">{{WEEKLY_COUNT}}</button><button type="button" class="token">{{WEEKLY_RANK}}</button><button type="button" class="token">{{WEEKLY_SUMMARY}}</button><button type="button" class="token">{{WEEKLY_GAP}}</button><button type="button" class="token">{{PRIZE_BOLD}}</button><button type="button" class="token">{{PRIZE_TABLE}}</button><button type="button" class="token">{{PRIZE_LINE}}</button><button type="button" class="token">{{DAY_DATE}}</button><button type="button" class="token">{{WEEK_DATE}}</button></div>
<textarea class="template" id="personal_template" name="personal_template" maxlength="6000" required>{_value(item.personal_template)}</textarea></div>
<div class="field"><label for="help_template">.도움말 전체 답변</label><div class="tokens" data-target="help_template"><button type="button" class="token">{{EVENT_TITLE_BOLD}}</button><button type="button" class="token">{{HELP_MESSAGE}}</button></div><textarea class="template" id="help_template" name="help_template" maxlength="4000" required>{_value(item.help_template)}</textarea></div>
</section><section class="card"><h2>실시간 미리보기</h2><div id="preview" class="preview"></div></section>
<div class="actions"><button class="save" type="submit">변경사항 저장</button></div></form>
<script>
const q=n=>document.querySelector(`[name="${{n}}"]`);const p=document.querySelector('#preview');
function fill(t,v){{Object.entries(v).forEach(([k,x])=>t=t.split('{{'+k+'}}').join(x));return t.replace(/\\n{{3,}}/g,'\\n\\n').trim();}}
function row(medal,name,count){{return fill(q('ranking_row_template').value,{{MEDAL:medal,POSITION:medal==='🥇'?'1':'2',NAME:name,NAME_BOLD:name,COUNT:count}});}}
function draw(){{const prizeMarkers={{1:'🥇',2:'🥈',3:'🥉',4:'▪'}};const prizes=[1,2,3,4].map(n=>q('prize_'+n).value.trim()?prizeMarkers[n]+n+'등 : '+q('prize_'+n).value.trim():null).filter(Boolean).join('\\n');
const prizeTable=prizes;const prizeLine=prizes?fill(q('prize_line_template').value,{{PRIZES:prizes}}):'';const rows=row('🥇','기강','850')+'\\n'+row('🥈','라온','790');
const common={{EVENT_TITLE:q('event_title').value,EVENT_TITLE_BOLD:q('event_title').value,DAILY_TITLE:q('daily_title').value,DAILY_TITLE_BOLD:q('daily_title').value,WEEKLY_TITLE:q('weekly_title').value,WEEKLY_TITLE_BOLD:q('weekly_title').value,DAY_DATE:'8월 22일',WEEK_DATE:'8월 17일 ~ 23일',DAILY_RANKING:rows,WEEKLY_RANKING:rows,PRIZE_LINE:prizeLine,FOOTER:q('footer').value}};
const rank=fill(q('ranking_template').value,common);const personal=fill(q('personal_template').value,{{NAME:'기강',NAME_BOLD:'기강',DAILY_COUNT:'120',DAILY_RANK:'1위',DAILY_SUMMARY:'120회 · 1위',DAILY_GAP:'현재 1위 👑',WEEKLY_COUNT:'850',WEEKLY_RANK:'1위',WEEKLY_SUMMARY:'850회 · 1위',WEEKLY_GAP:'현재 1위 👑',PRIZE:q('prize_1').value||'순위권 밖',PRIZE_BOLD:q('prize_1').value||'순위권 밖',PRIZE_TABLE:prizeTable,PRIZE_LINE:prizeLine,DAY_DATE:'8월 22일',WEEK_DATE:'8월 17일 ~ 23일'}});
const help=fill(q('help_template').value,{{EVENT_TITLE:q('event_title').value,EVENT_TITLE_BOLD:q('event_title').value,HELP_MESSAGE:q('help_message').value}});p.textContent='[.채팅순위]\\n'+rank+'\\n\\n[.나]\\n'+personal+'\\n\\n[.도움말]\\n'+help;}}
document.querySelectorAll('.tokens').forEach(box=>box.querySelectorAll('.token').forEach(btn=>btn.addEventListener('click',()=>{{const el=document.getElementById(box.dataset.target);const a=el.selectionStart,b=el.selectionEnd;el.value=el.value.slice(0,a)+btn.textContent+el.value.slice(b);el.focus();el.setSelectionRange(a+btn.textContent.length,a+btn.textContent.length);draw();}})));
document.querySelectorAll('input,textarea').forEach(el=>el.addEventListener('input',draw));draw();
</script>"""
    return _layout(content, f"{group.title} 설정")


def _field(data: dict[str, list[str]], name: str, maximum: int) -> str:
    return data.get(name, [""])[0].strip()[:maximum]


def _settings_from_form(chat_id: int, data: dict[str, list[str]]) -> ChatSettings:
    defaults = ChatSettings(chat_id=chat_id)

    def template_value(name: str, maximum: int, default: str) -> str:
        return _field(data, name, maximum) if name in data else default

    try:
        top_limit = int(_field(data, "top_limit", 2) or "10")
    except ValueError:
        top_limit = 10
    return ChatSettings(
        chat_id=chat_id,
        event_title=_field(data, "event_title", 255),
        daily_title=_field(data, "daily_title", 255),
        weekly_title=_field(data, "weekly_title", 255),
        prize_1=_field(data, "prize_1", 100),
        prize_2=_field(data, "prize_2", 100),
        prize_3=_field(data, "prize_3", 100),
        prize_4=_field(data, "prize_4", 100),
        footer=_field(data, "footer", 1000),
        help_message=_field(data, "help_message", 2000),
        top_limit=max(3, min(50, top_limit)),
        ranking_template=template_value(
            "ranking_template", 6000, defaults.ranking_template
        ),
        personal_template=template_value(
            "personal_template", 6000, defaults.personal_template
        ),
        help_template=template_value("help_template", 4000, defaults.help_template),
        ranking_row_template=template_value(
            "ranking_row_template", 500, defaults.ranking_row_template
        ),
        prize_line_template=template_value(
            "prize_line_template", 500, defaults.prize_line_template
        ),
        empty_ranking_message=template_value(
            "empty_ranking_message", 500, defaults.empty_ranking_message
        ),
    )


def create_http_server(
    storage: Storage,
    settings: WebSettings,
    host: str = "0.0.0.0",
    port: int | None = None,
) -> ThreadingHTTPServer:
    class AdminHandler(BaseHTTPRequestHandler):
        server_version = "ChatRankAdmin/1.0"

        def _send(
            self,
            status: int,
            body: str,
            content_type: str = "text/html; charset=utf-8",
            headers: dict[str, str] | None = None,
        ) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(encoded)

        def _redirect(self, location: str, status: int = 303) -> None:
            self._send(status, "", headers={"Location": location})

        def _authorized(self) -> bool:
            if _valid_auth(self.headers.get("Authorization", ""), settings):
                return True
            self._send(
                401,
                "관리자 로그인이 필요합니다.",
                "text/plain; charset=utf-8",
                {"WWW-Authenticate": 'Basic realm="Chat Ranking Admin"'},
            )
            return False

        @staticmethod
        def _chat_id(path: str) -> int | None:
            prefix = "/admin/chat/"
            if not path.startswith(prefix):
                return None
            try:
                return int(path[len(prefix) :])
            except ValueError:
                return None

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path == "/health":
                self._send(200, "ok", "text/plain; charset=utf-8")
                return
            if parsed.path == "/":
                self._redirect("/admin", 302)
                return
            if not self._authorized():
                return
            if parsed.path == "/admin":
                self._send(200, _chat_list(storage.list_chats()))
                return
            chat_id = self._chat_id(parsed.path)
            if chat_id is None:
                self._send(404, "페이지를 찾을 수 없습니다.", "text/plain; charset=utf-8")
                return
            groups = {group.chat_id: group for group in storage.list_chats()}
            group = groups.get(chat_id)
            if not group:
                self._send(404, "등록되지 않은 소통방입니다.", "text/plain; charset=utf-8")
                return
            saved = parse_qs(parsed.query).get("saved") == ["1"]
            self._send(200, _edit_form(group, storage.get_chat_settings(chat_id), saved))

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                return
            parsed = urlsplit(self.path)
            chat_id = self._chat_id(parsed.path)
            groups = {group.chat_id: group for group in storage.list_chats()}
            group = groups.get(chat_id) if chat_id is not None else None
            if chat_id is None or not group:
                self._send(404, "등록되지 않은 소통방입니다.", "text/plain; charset=utf-8")
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_length = 0
            if content_length > 100_000:
                self._send(413, "입력 내용이 너무 큽니다.", "text/plain; charset=utf-8")
                return
            body = self.rfile.read(content_length)
            try:
                data = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            except UnicodeDecodeError:
                self._send(400, "잘못된 입력입니다.", "text/plain; charset=utf-8")
                return
            item = _settings_from_form(chat_id, data)
            required = (
                item.event_title,
                item.daily_title,
                item.weekly_title,
                item.ranking_template,
                item.personal_template,
                item.help_template,
                item.ranking_row_template,
                item.empty_ranking_message,
            )
            if not all(required):
                self._send(422, _edit_form(group, item, False, "제목과 필수 답변 칸은 비워둘 수 없습니다."))
                return
            storage.save_chat_settings(item)
            self._redirect(f"/admin/chat/{chat_id}?saved=1")

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.info("Admin web: " + format, *args)

    server = ThreadingHTTPServer((host, settings.port if port is None else port), AdminHandler)
    server.daemon_threads = True
    return server


def start_admin_server(storage: Storage, settings: WebSettings) -> threading.Thread:
    server = create_http_server(storage, settings)
    thread = threading.Thread(target=server.serve_forever, name="admin-web", daemon=True)
    thread.start()
    return thread
