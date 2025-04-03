document.addEventListener('DOMContentLoaded', function() {
    // 收藏按钮点击事件
    document.querySelectorAll('.collect-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const videoData = {
                bvid: this.dataset.bvid,
                title: this.dataset.title,
                heat: this.dataset.heat
            };

            try {
                const response = await fetch('/add_favorite', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(videoData)
                });

                if (response.ok) {
                    this.innerHTML = '❤️ 已收藏';
                    this.disabled = true;
                }
            } catch (error) {
                console.error('收藏失败:', error);
            }
        });
    });
});