"""Public operator email UI. Does not send email or read the current page URL."""
import html
import re
from urllib.parse import quote

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def contact_mailto(app_name: str, email: str) -> str | None:
    email = email.strip()
    if not _EMAIL.fullmatch(email):
        return None
    subject = "[" + app_name + "] お問い合わせ"
    body = "お問い合わせ内容：\r\n\r\n"
    return "mailto:" + quote(email, safe="@") + "?subject=" + quote(subject, safe="") + "&body=" + quote(body, safe="")

def contact_panel(app_name: str, email: str) -> tuple[str, str]:
    mailto = contact_mailto(app_name, email)
    if not mailto:
        return '<div class="shell"><p>メール窓口は現在利用できません。下のサイト内受付をご利用ください。</p></div>', ""
    escaped_email = html.escape(email.strip(), quote=True)
    panel = """
    <style>
    .business-support{background:#fff;border:1px solid #dae3e1;border-radius:16px;padding:clamp(20px,4vw,32px);margin:28px auto;max-width:860px}
    .business-support h2{margin:0 0 16px}.business-support p{line-height:1.8;margin:14px 0}
    .business-support label{display:block;font-weight:700}.business-support input{box-sizing:border-box;max-width:460px;width:100%;padding:12px;font-size:16px;margin:8px 0 18px;border:1px solid #a5b8b4;border-radius:8px}
    .business-support-actions{display:flex;gap:12px;flex-wrap:wrap}.business-support-actions .btn{min-height:44px;justify-content:center}
    .business-support :is(a,button,input):focus-visible{outline:3px solid #17664f;outline-offset:3px}
    @media(max-width:520px){.business-support-actions{display:grid}.business-support-actions .btn{width:100%}}
    </style>
    <div class="shell"><section class="business-support" aria-labelledby="email-contact-heading">
    <h2 id="email-contact-heading">メールでのお問い合わせ</h2>
    <label for="operator-contact-email">メールアドレス</label>
    <input id="operator-contact-email" type="text" inputmode="email" readonly value="__EMAIL__">
    <div class="business-support-actions"><a class="btn btn-primary" href="__MAILTO__">メールで問い合わせる</a>
    <button class="btn btn-outline" type="button" id="copy-operator-email">メールアドレスをコピー</button></div>
    <p>メールアプリが開きます。内容を入力して送信してください。</p>
    <p>開かない場合は、アドレスをコピーして普段お使いのメールから送信できます。</p>
    <p role="status" aria-live="polite" id="copy-operator-email-status"></p>
    </section></div>
    """.replace("__EMAIL__", escaped_email).replace("__MAILTO__", html.escape(mailto, quote=True))
    script = """
    <script>
    (()=>{const button=document.getElementById("copy-operator-email"),input=document.getElementById("operator-contact-email"),status=document.getElementById("copy-operator-email-status");
    button.addEventListener("click",async()=>{try{if(!navigator.clipboard?.writeText)throw new Error("unavailable");await navigator.clipboard.writeText(input.value);status.textContent="メールアドレスをコピーしました。"}catch{input.focus();input.select();status.textContent="コピーできませんでした。メールアドレスを選択して手動でコピーしてください。";}});})();
    </script>
    """
    return panel, script
