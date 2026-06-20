const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const P = require('pino');
const fs = require('fs');

const AUTH_FOLDER = `./auth_${Date.now()}`;

async function cleanup() {
    try {
        if (fs.existsSync(AUTH_FOLDER)) fs.rmSync(AUTH_FOLDER, { recursive: true, force: true });
    } catch (e) {}
}

async function checkNumber(number) {
    await cleanup();
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        logger: P({ level: 'silent' }),
        auth: state,
        browser: ['Chrome (Linux)', '', ''],
    });

    return new Promise((resolve) => {
        let resolved = false;
        const timeout = setTimeout(() => {
            if (!resolved) resolve(`${number}:unused`);
            cleanup();
        }, 25000);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect } = update;

            if (connection === 'open') {
                resolved = true;
                clearTimeout(timeout);
                resolve(`${number}:used`);
                sock.end();
                cleanup();
            }

            if (lastDisconnect?.error) {
                const err = lastDisconnect.error.toString().toLowerCase();
                resolved = true;
                clearTimeout(timeout);
                if (err.includes("403") || err.includes("ban") || err.includes("blocked") || 
                    err.includes("spam") || err.includes("can't use") || err.includes("not allowed")) {
                    resolve(`${number}:banned`);
                } else if (err.includes("messenger") || err.includes("switch") || err.includes("restricted")) {
                    resolve(`${number}:personal`);
                } else {
                    resolve(`${number}:unused`);
                }
                sock.end();
                cleanup();
            }
        });

        sock.ev.on('creds.update', saveCreds);

        setTimeout(() => {
            sock.requestPairingCode(number).catch(err => {
                const msg = err.message.toLowerCase();
                if (msg.includes("ban") || msg.includes("403") || msg.includes("blocked") || msg.includes("spam")) {
                    if (!resolved) resolve(`${number}:banned`);
                } else if (msg.includes("messenger") || msg.includes("switch")) {
                    resolve(`${number}:personal`);
                }
            });
        }, 1800);
    });
}

(async () => {
    const input = process.argv[2];
    if (!input) process.exit(1);

    const numbers = input.split(',').map(n => n.trim()).filter(Boolean);
    const results = [];

    for (const num of numbers) {
        const result = await checkNumber(num);
        results.push(result);
        await new Promise(r => setTimeout(r, 4200));
    }

    console.log(`CHECK_RESULT:${results.join("|")}`);
    await cleanup();
})();
