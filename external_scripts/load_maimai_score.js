javascript:(async function() {
    /* Configuration */
    const host = window.location.hostname;
    const baseUrl = "https://" + host + "/maimai-mobile/record/";
    const b15VersionIds = host.includes("maimaidx-eng.com") ? [24, 25] : [25, 26];

    const CONFIG = {
        allUrl: baseUrl + "musicGenre/search/?genre=99&diff=",
        versionUrl: (versionId, diffId) => baseUrl + "musicVersion/search/?version=" + versionId + "&diff=" + diffId,
        difficulties: [
            { id: 0, name: "Basic" },
            { id: 1, name: "Advanced" },
            { id: 2, name: "Expert" },
            { id: 3, name: "Master" },
            { id: 4, name: "Re:MASTER" }
        ],
        versions: [
            { id: 24, name: "PRiSM PLUS" },
            { id: 25, name: "CiRCLE" },
            { id: 26, name: "CiRCLE PLUS" }
        ],
        b15Versions: undefined
    };
    CONFIG.b15Versions = CONFIG.versions.filter(v => b15VersionIds.includes(v.id))

    const statusDiv = document.createElement("div");
    let allScores = [];
    let newSongs = new Set();

    function showStatus(msg) {
        statusDiv.style.cssText = "position:fixed;top:10px;left:10px;z-index:9999;background:rgba(0,0,0,0.8);color:white;padding:15px;border-radius:5px;font-family:sans-serif;font-size:14px;";
        statusDiv.innerText = msg;
        if (!document.body.contains(statusDiv)) {
            document.body.appendChild(statusDiv);
        }
        console.log(msg);
    }

    function getChartType(row) {
        if (row.id && row.id.includes("sta_")) return "Standard";
        if (row.querySelector(".music_standard_score_back")) return "Standard";
        const img = row.querySelector("img.music_kind_icon");
        if (img && img.src.includes("_standard")) return "Standard";
        return "DX";
    }

    function getIconStatus(img) {
        if (!img) return "none";
        /* Extract filename from src (e.g., https://.../music_icon_sync.png?ver=1.50 -> music_icon_sync) */
        const filename = img.src.split('/').pop().split('?')[0].split('.')[0];
        
        /* Remove prefix "music_icon_" */
        const status = filename.replace("music_icon_", "");
        
        /* Map "back" to "none", otherwise return the status (e.g., "sync", "fc", "app") */
        return status === "back" ? "none" : status;
    }

    async function fetchAllScores() {        
        for (const diff of CONFIG.difficulties) {
            showStatus("Fetching " + diff.name + " scores...");
            
            const response = await fetch(CONFIG.allUrl + diff.id);
            if (!response.ok) throw new Error("HTTP " + response.status);
            
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');

            const scoreRows = doc.querySelectorAll('.w_450.m_15.p_r.f_0');

            scoreRows.forEach(row => {
                const songNameElem = row.querySelector('.music_name_block');
                const scoreElem = row.querySelector('.music_score_block');
                const levelElem = row.querySelector('.music_lv_block');
                const dxScoreElem = row.querySelector('.music_score_block.w_190');
                
                /* Select all status icons (Sync, Combo, Rank) */
                const icons = row.querySelectorAll('img.h_30.f_r');

                if (songNameElem && scoreElem) {
                    /* Parse DX Score (e.g., "1,713 / 1,902" -> 1713) */
                    let dxScore = 0, maxDxScore = 0;
                    if (dxScoreElem) {
                        const dxText = dxScoreElem.innerText.trim().split('/');
                        dxScore = parseInt(dxText[0].replace(/,/g, ''), 10);
                        maxDxScore = parseInt(dxText[1].replace(/,/g, ''), 10);
                    }

                    /* Parse Sync and Combo from icons */
                    /* Index 0 is Sync, Index 1 is Combo (based on DOM order in provided snippet) */
                    const syncStatus = icons.length > 0 ? getIconStatus(icons[0]) : "none";
                    const comboStatus = icons.length > 1 ? getIconStatus(icons[1]) : "none";

                    allScores.push({
                        songName: songNameElem.innerText,
                        difficulty: diff.name,
                        level: levelElem ? levelElem.innerText.trim() : "Unknown",
                        achievement: scoreElem.innerText.trim(),
                        dxscore: dxScore,
                        sync: syncStatus,
                        combo: comboStatus,
                        type: getChartType(row),
                        raw_difficulty_id: diff.id,
                        isNew: false,
                    });
                }
            });
            
            /* Wait 500ms between requests */
            await new Promise(r => setTimeout(r, 500));
        }
    }

    async function fetchNewSongs() {        
        for (const ver of CONFIG.b15Versions) {
            showStatus("Fetching " + ver.name + " songs...");
            
            const response = await fetch(CONFIG.versionUrl(ver.id, 0));
            if (!response.ok) throw new Error("HTTP " + response.status);
            
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');

            const songRows = doc.querySelectorAll('.w_450.m_15.p_3.f_0');
            // showStatus("Fetched " + songRows.length + " songs")

            songRows.forEach(row => {
                const songNameElem = row.querySelector('.music_name_block')
                if (songNameElem) {
                    newSongs.add(songNameElem.innerText + "_" + getChartType(row));
                }
            });
            
            /* Wait 500ms between requests */
            await new Promise(r => setTimeout(r, 500));
        }
    }

    try {
        showStatus("Starting export... Please wait.");
        
        await fetchAllScores();
        await fetchNewSongs();

        showStatus("Filtering B15 songs for version " + CONFIG.b15Versions[0].name + " and " + CONFIG.b15Versions[1].name + "...")

        allScores.forEach(s => {
            if (newSongs.has(s.songName + "_" + s.type)) {
                s.isNew = true;
            }
        });

        showStatus("Export complete! Generating JSON for " + allScores.length + " scores...");

        const jsonStr = JSON.stringify(allScores, null, 2);
        const blob = new Blob([jsonStr], { type: "application/json" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = "maimai_scores_" + new Date().toISOString().slice(0,10) + ".json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        setTimeout(() => { if(statusDiv) statusDiv.remove(); }, 4000);

    } catch (err) {
        console.error(err);
        showStatus("Error: " + err.message);
        alert("An error occurred. Please check the console (F12) for details.");
    }
})();