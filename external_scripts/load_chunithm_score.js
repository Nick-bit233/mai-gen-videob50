javascript:(async function () {
    "use strict";

    const host = window.location.hostname;
    const isChunithmNet = host === "chunithm-net-eng.com" ||
        host === "chunithm-net.com" || host.endsWith(".chunithm-net.com");
    const mobilePathMatch = window.location.pathname.match(/^(.*\/mobile)(?:\/|$)/);
    // International CHUNITHM-NET uses /mobile. Japanese deployments may put
    // the same mobile application below an additional path prefix.
    const baseUrl = window.location.origin + (mobilePathMatch ? mobilePathMatch[1] : "/mobile");

    const CONFIG = {
        metadataUrl: "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/chuni_fusion_data.json",
        pages: [
            {
                name: "Best",
                url: baseUrl + "/home/playerData/ratingDetailBest/",
                isNew: false
            },
            {
                name: "Current",
                url: baseUrl + "/home/playerData/ratingDetailRecent/",
                isNew: true
            }
        ],
        requestDelayMs: 500
    };

    const difficultyById = {
        0: "BASIC",
        1: "ADVANCED",
        2: "EXPERT",
        3: "MASTER",
        4: "ULTIMA"
    };

    const statusDiv = document.createElement("div");

    function showStatus(message) {
        statusDiv.style.cssText = "position:fixed;top:10px;left:10px;z-index:9999;background:rgba(0,0,0,.82);color:#fff;padding:15px;border-radius:5px;font-family:sans-serif;font-size:14px;";
        statusDiv.innerText = message;
        if (!document.body.contains(statusDiv)) document.body.appendChild(statusDiv);
        console.log(message);
    }

    function normalizeDifficulty(rawDifficulty, difficultyId) {
        if (difficultyId in difficultyById) return difficultyById[difficultyId];
        const normalized = String(rawDifficulty || "").trim().toUpperCase();
        return normalized || "Unknown";
    }

    function parseScore(text) {
        const parsed = Number.parseInt(String(text || "").replace(/[^0-9]/g, ""), 10);
        return Number.isNaN(parsed) ? null : parsed;
    }

    function round(value, digits) {
        const factor = 10 ** digits;
        return Math.round((value + Number.EPSILON) * factor) / factor;
    }

    function computeChartRating(chartConstant, score) {
        const ds = Number(chartConstant);
        const s = Number(score);
        if (!(ds > 0) || !Number.isFinite(s)) return null;

        let bonus;
        if (s >= 1009000) bonus = 2.15;
        else if (s >= 1007500) bonus = Math.min(2 + Math.floor((s - 1007500) / 100) * 0.01, 2.15);
        else if (s >= 1005000) bonus = Math.min(1.5 + Math.floor((s - 1005000) / 50) * 0.01, 2);
        else if (s >= 1000000) bonus = Math.min(1 + Math.floor((s - 1000000) / 100) * 0.01, 1.5);
        else if (s >= 990000) bonus = Math.min(0.6 + Math.floor((s - 990000) / 250) * 0.01, 1);
        else if (s >= 975000) bonus = Math.min(Math.floor((s - 975000) / 250) * 0.01, 0.6);
        else if (s >= 950000) bonus = -1.5;
        else if (s >= 925000) bonus = -3;
        else if (s >= 900000) bonus = -5;
        else if (s >= 800000) return round((ds - 5) / 2, 2);
        else return 0;

        return round(ds + bonus, 2);
    }

    async function fetchMetadata() {
        showStatus("Fetching CHUNITHM chart constants...");
        const response = await fetch(CONFIG.metadataUrl);
        if (!response.ok) throw new Error("Metadata returned HTTP " + response.status);
        const metadata = await response.json();
        if (!Array.isArray(metadata)) throw new Error("CHUNITHM metadata has an unexpected format");
        return metadata;
    }

    function getChartConstant(chart) {
        // These samples come from the current JP/international version, so prefer
        // the latest constant and use the CN constant only as a fallback.
        const latest = Number(chart.level_value_latest);
        if (latest > 0) return latest;
        const cn = Number(chart.level_value_cn);
        return cn > 0 ? cn : null;
    }

    function normalizeTitle(title) {
        return String(title || "").normalize("NFKC").replace(/\s+/g, " ").trim();
    }

    function addRatings(scores, metadata) {
        const songsByTitle = new Map();
        metadata.forEach(song => {
            const names = [song.title].concat(Array.isArray(song.aliases) ? song.aliases : []);
            names.forEach(name => {
                const title = normalizeTitle(name);
                if (!title) return;
                if (!songsByTitle.has(title)) songsByTitle.set(title, []);
                if (!songsByTitle.get(title).includes(song)) songsByTitle.get(title).push(song);
            });
        });

        const missing = [];
        scores.forEach(record => {
            const songs = songsByTitle.get(normalizeTitle(record.songName)) || [];
            const matchingCharts = songs.flatMap(song => song.charts_info || [])
                .filter(chart => Number(chart.difficulty) === record.difficultyId);
            const chartConstant = matchingCharts.map(getChartConstant).find(value => value !== null);
            if (chartConstant === undefined) {
                missing.push(record.songName + " [" + record.difficulty + "]");
                return;
            }
            record.chartConstant = chartConstant;
            record.chartRating = computeChartRating(chartConstant, record.score);
        });

        if (missing.length > 0) {
            throw new Error("No chart constant found for: " + Array.from(new Set(missing)).join(", "));
        }
    }

    function averageRating(scores) {
        if (scores.length === 0) return 0;
        return round(scores.reduce((sum, record) => sum + record.chartRating, 0) / scores.length, 4);
    }

    function parseScores(doc, isNew) {
        return Array.from(doc.querySelectorAll(".musiclist_box")).map((row, sourceIndex) => {
            const titleElement = row.querySelector(".music_title");
            const scoreElement = row.querySelector(".play_musicdata_highscore .text_b");
            const difficultyInput = row.querySelector('input[name="diff"]');
            const songIdInput = row.querySelector('input[name="idx"]');
            const difficultyClass = Array.from(row.classList).find(name => name.startsWith("bg_"));
            const rawDifficulty = difficultyClass ? difficultyClass.slice(3) : "";
            const difficultyId = difficultyInput
                ? Number.parseInt(difficultyInput.value, 10)
                : Object.entries(difficultyById).find(([, name]) => name.toUpperCase() === rawDifficulty.toUpperCase())?.[0];
            const score = parseScore(scoreElement ? scoreElement.textContent : "");

            if (!titleElement || score === null || !Number.isInteger(Number(difficultyId))) {
                console.warn("Skipping an incomplete CHUNITHM score row", row);
                return null;
            }

            return {
                songName: titleElement.textContent.trim(),
                difficulty: normalizeDifficulty(rawDifficulty, Number(difficultyId)),
                difficultyId: Number(difficultyId),
                score: score,
                songId: songIdInput ? songIdInput.value : null,
                isNew: isNew,
                sourceIndex: sourceIndex
            };
        }).filter(Boolean);
    }

    async function fetchPage(page) {
        showStatus("Fetching CHUNITHM " + page.name + " scores...");
        const response = await fetch(page.url, { credentials: "same-origin" });
        if (!response.ok) throw new Error(page.name + " page returned HTTP " + response.status);
        const html = await response.text();
        const doc = new DOMParser().parseFromString(html, "text/html");
        const scores = parseScores(doc, page.isNew);
        if (scores.length === 0) {
            throw new Error("No scores found on the " + page.name + " page. The CHUNITHM-NET layout may have changed.");
        }
        return scores;
    }

    async function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return;
        }
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.cssText = "position:fixed;left:-9999px;top:0;";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const copied = document.execCommand("copy");
        textarea.remove();
        if (!copied) throw new Error("The browser rejected clipboard access");
    }

    function addCopyButton(jsonText, bestCount, currentCount) {
        document.getElementById("maigen-chunithm-copy-button")?.remove();
        const button = document.createElement("button");
        button.id = "maigen-chunithm-copy-button";
        button.innerText = "📋 Copy CHUNITHM score data";
        button.title = bestCount + " Best + " + currentCount + " Current records";
        button.style.cssText = "position:fixed;top:10px;left:10px;z-index:10000;padding:10px 16px;background:#7b6ce7;color:white;border:0;border-radius:6px;font-size:14px;cursor:pointer;";
        button.onclick = async () => {
            try {
                await copyText(jsonText);
                button.innerText = "✅ Copied " + (bestCount + currentCount) + " scores";
                setTimeout(() => { button.innerText = "📋 Copy CHUNITHM score data"; }, 10000);
            } catch (error) {
                alert("Copy failed: " + error.message);
            }
        };
        document.body.appendChild(button);
    }

    try {
        if (!isChunithmNet) {
            throw new Error("Run this bookmarklet on CHUNITHM-NET after logging in.");
        }

        showStatus("Starting CHUNITHM score export...");
        const bestScores = await fetchPage(CONFIG.pages[0]);
        await new Promise(resolve => setTimeout(resolve, CONFIG.requestDelayMs));
        const currentScores = await fetchPage(CONFIG.pages[1]);
        const metadata = await fetchMetadata();
        addRatings(bestScores, metadata);
        addRatings(currentScores, metadata);
        const allScores = bestScores.concat(currentScores);
        const bestAverage = averageRating(bestScores);
        const currentAverage = averageRating(currentScores);
        const rating = averageRating(allScores);
        const output = {
            gameType: "chunithm",
            host: host,
            rating: rating,
            bestAverage: bestAverage,
            currentAverage: currentAverage,
            scores: allScores
        };
        const jsonText = JSON.stringify(output, null, 2);

        addCopyButton(jsonText, bestScores.length, currentScores.length);
        showStatus("Exported " + bestScores.length + " Best and " + currentScores.length + " Current scores. Rating: " + rating.toFixed(4));
        setTimeout(() => statusDiv.remove(), 5000);
    } catch (error) {
        console.error(error);
        showStatus("Error: " + error.message);
        alert("CHUNITHM export failed. Check the browser console (F12) for details.");
    }
})();
