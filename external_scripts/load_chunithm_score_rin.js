javascript:(async function() {
    const host = window.location.hostname;
    const baseUrl = "https://portal.naominet.live/";

    const CONFIG = {
        ratingUrl: baseUrl + "chuni/v2/rating",
        difficulties: [
            { id: 0, name: "Basic" },
            { id: 1, name: "Advanced" },
            { id: 2, name: "Expert" },
            { id: 3, name: "Master" },
            { id: 4, name: "Ultima" }
        ],
    };

    const statusDiv = document.createElement("div");

    function showStatus(msg) {
        statusDiv.style.cssText = "position:fixed;top:10px;left:10px;z-index:9999;background:rgba(0,0,0,0.8);color:white;padding:15px;border-radius:5px;font-family:sans-serif;font-size:14px;";
        statusDiv.innerText = msg;
        if (!document.body.contains(statusDiv)) {
            document.body.appendChild(statusDiv);
        }
        console.log(msg);
    }

    async function fetchRatingData() {
        /* ============================================================
         * 说明：/chuni/v2/rating 是 Angular SPA 路由，fetch 会返回静态壳页面，不含真实数据。
         * 成绩卡片是由前端异步渲染到当前 DOM 中的，因此直接解析 document。
         * ============================================================ */

        /* ===== 调试：在控制台输出当前页面上的 rating-card 数量 ===== */
        console.log("[CHUNI] document readyState:", document.readyState);
        console.log("[CHUNI] rating-card count:", document.querySelectorAll('.rating-card').length);
        /* ========================================================== */

        const doc = document;
        
        /* ============================================================
         * 提取总评级
         * 遍历所有 class 包含 list-group-item 的 div（共 2 个），提取首个：
         *  <li _ngcontent-ng-c2503884326="" class="list-group-item"><div _ngcontent-ng-c2503884326="">你的评级 ： 16.00</div></li>
         *  保留两位小数
         * ============================================================ */
        const rating_elem = doc.querySelectorAll('.list-group-item')[0];
        const rating_text = rating_elem ? rating_elem.innerText.trim() : '';
        const rating_match = rating_text.match(/你的评级 ：\s*([\d.]+)/);
        const rating_value = rating_match ? parseFloat(rating_match[1]).toFixed(2) : null;

        /* ============================================================
         * 分析逻辑
         * 遍历所有 class 包含 rating-card 的 div（最多 50 个），提取：
         *   - rankElem    排名（如 #6）
         *   - songNameElem 曲名（如 Cryogenic）
         *   - scoreElem   分数（如 1007846）
         *   - levelElem   难度等级（如 Master 14.0）
         *   - ratingElem  Rating 值（如 16.03）
         * ============================================================ */
        const scores = [];
        let isNewSong = false;

        const cards = doc.querySelectorAll('.rating-card');
        cards.forEach(card => {
            /* 排名 + 曲名：同一行 .fw-bold 内，<span> 是排名，其余文本是曲名 */
            const titleElem = card.querySelector('.fw-bold');
            const rankElem = card.querySelector('.fw-bold span');
            let songNameElem = '';
            if (titleElem && rankElem) {
                const fullText = titleElem.textContent;
                const rankText = rankElem.textContent;
                
                /* 格式：rankText + ' ' + songName */
                songNameElem = fullText.substring(rankText.length + 1);
            }

            /* 分数：第二个 .text-truncate（第一个是排名+曲名行） */
            const truncateElems = card.querySelectorAll('.text-truncate');
            const scoreElem = truncateElems.length > 1
                ? truncateElems[1].innerText.trim()
                : '';

            /* 难度等级：.rating-score 内的 difficulty-* badge */
            const levelElem = card.querySelector('.rating-score [class*="difficulty-"]');
            const level = levelElem ? levelElem.innerText.trim() : '';
            const [difficulty, ds] = level.split(' ');

            /* 根据 difficulty 反向查找 id 作为 difficultyId */
            const diffEntry = CONFIG.difficulties.find(d => d.name === difficulty);
            const difficultyId = diffEntry ? diffEntry.id : -1;

            /* Rating 值：.score-value span */
            const ratingElem = card.querySelector('.score-value');
            const rating = ratingElem ? ratingElem.innerText.trim() : '';

            /* isNew：第一个#1起为true，第二个#1起为false */
            const rank = rankElem ? rankElem.innerText.trim() : '';
            if (rank === "#1") isNewSong = !isNewSong;
            const isNew = isNewSong;

            scores.push({
                rank: rank,
                songName: songNameElem,
                score: scoreElem,
                difficulty: difficulty,
                ds: ds,
                difficultyId: difficultyId,
                rating: rating,
                isNew: isNew,
            });
        });

        const analysisResult = {
            host: host,
            count: scores.length,
            rating: rating_value,
            scores: scores,
        };

        return analysisResult;
    }

    try {
        /* ===== 检测：必须位于 rating 页面，否则只显示警告，不执行任何内容 ===== */
        const currentUrl = window.location.href;
        const targetPath = CONFIG.ratingUrl.replace(/^https?:\/\/[^/]+/, '');

        if (!currentUrl.includes(targetPath)) {
            showStatus("错误：请在 评级/Rating 页面运行本脚本。当前页面: " + currentUrl);

            const warnBtn = document.createElement('button');
            warnBtn.innerText = "⚠️ 请在 评级/Rating 页面运行脚本";
            warnBtn.style.cssText = "position:fixed;top:10px;left:10px;z-index:9999;padding:10px 16px;background:#DF6B57;color:white;border:none;border-radius:6px;font-size:14px;cursor:pointer;";
            document.body.appendChild(warnBtn);

            setTimeout(() => {
                warnBtn.remove();
                if (statusDiv) statusDiv.remove();
            }, 5000);

            return;
        }
        /* ================================================================ */

        showStatus("Starting export... Please wait.");

        const result = await fetchRatingData();

        showStatus("Export complete! Generating JSON...");
        const jsonStr = JSON.stringify(result, null, 2);

        const btn = document.createElement('button');
        btn.innerText = "📋 点击复制CHUNITHM成绩数据 (RinNET)";
        btn.style.cssText = "position:fixed;top:10px;left:10px;z-index:9999;padding:10px 16px;background:#E7B1A9;color:white;border:none;border-radius:6px;font-size:14px;cursor:pointer;transition:background 0.2s,transform 0.1s;";
        btn.onmousedown = () => {
            btn.style.transform = "scale(0.95)";
            btn.style.background = "#c98880";
        };
        btn.onmouseup = () => {
            btn.style.transform = "scale(1)";
            btn.style.background = "#E7B1A9";
        };
        btn.onmouseleave = () => {
            btn.style.transform = "scale(1)";
            btn.style.background = "#E7B1A9";
        };
        btn.onclick = () => {
            navigator.clipboard.writeText(jsonStr).then(() => {
                btn.innerText = "✅ 已复制！";
                setTimeout(() => {
                    btn.innerText = "📋 复制成绩数据";
                }, 10000);
            }).catch(err => {
                alert("复制失败: " + err.message);
            });
        };
        document.body.appendChild(btn);

        setTimeout(() => { if(statusDiv) statusDiv.remove(); }, 5000);

    } catch (err) {
        console.error(err);
        showStatus("Error: " + err.message);
        alert("An error occurred. Please check the console (F12) for details.");
    }
})();
