// GitHub'ın zamanlayıcısı tetikleri sık atladığı için botu Cloudflare'in zamanlayıcısıyla başlatır.
// Ne zaman paylaşılacağına yine botun planlayıcısı karar verir; burası sadece "uyan" der.
const ADRES = "https://api.github.com/repos/yigitkumsal2026-wq/dustumu/actions/workflows/bot.yml/dispatches";

export default {
  async scheduled(_olay, env) {
    const yanit = await fetch(ADRES, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        // trim: anahtar kaydedilirken PowerShell başına görünmez BOM karakteri ekledi.
        Authorization: `Bearer ${env.GITHUB_TOKEN.trim()}`,
        "User-Agent": "dustumu-tetikleyici",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    if (!yanit.ok) {
      throw new Error(`GitHub ${yanit.status}: ${await yanit.text()}`);
    }
  },
};
