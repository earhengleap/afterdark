/**
 * XVideo Gallery - Real Video Thumbnails
 * Generates actual video frame thumbnails, not colored placeholders
 */

class VideoGalleryApp {
    constructor() {
        this.videos = [];
        this.filteredVideos = [];
        this.currentVideo = null;
        this.currentSort = 'date-desc';
        this.currentFilter = 'all';
        this.searchTerm = '';
        this.gridCompact = false;
        this.lastUpdate = new Date();
        this.thumbnailCache = new Map();
        this.processingThumbnails = new Set();
        
        this.elements = {
            videoGrid: document.getElementById('videoGrid'),
            videoModal: document.getElementById('videoModal'),
            modalOverlay: document.getElementById('modalOverlay'),
            modalClose: document.getElementById('modalClose'),
            modalVideo: document.getElementById('modalVideo'),
            modalTitle: document.getElementById('modalTitle'),
            modalFilename: document.getElementById('modalFilename'),
            modalSize: document.getElementById('modalSize'),
            modalDate: document.getElementById('modalDate'),
            modalResolution: document.getElementById('modalResolution'),
            downloadBtn: document.getElementById('downloadBtn'),
            shareBtn: document.getElementById('shareBtn'),
            likeBtn: document.getElementById('likeBtn'),
            relatedGrid: document.getElementById('relatedGrid'),
            searchInput: document.getElementById('searchInput'),
            searchClear: document.getElementById('searchClear'),
            sortSelect: document.getElementById('sortSelect'),
            refreshBtn: document.getElementById('refreshBtn'),
            gridToggle: document.getElementById('gridToggle'),
            videoCount: document.getElementById('videoCount'),
            emptyState: document.getElementById('emptyState'),
            toast: document.getElementById('toast'),
            toastMessage: document.getElementById('toastMessage'),
            totalVideos: document.getElementById('totalVideos'),
            totalSize: document.getElementById('totalSize'),
            recentVideos: document.getElementById('recentVideos'),
            serverPath: document.getElementById('serverPath'),
            lastUpdate: document.getElementById('lastUpdate')
        };
        
        this.init();
    }

    async init() {
        console.log('🎬 Initializing XVideo Gallery...');
        this.setupEventListeners();
        await this.loadVideos();
        this.startAutoRefresh();
        console.log('✅ Gallery initialized');
    }

    setupEventListeners() {
        this.elements.searchInput?.addEventListener('input', (e) => this.handleSearch(e));
        this.elements.searchClear?.addEventListener('click', () => this.clearSearch());
        
        this.elements.sortSelect?.addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.applyFilters();
        });
        
        this.elements.refreshBtn?.addEventListener('click', () => this.refreshVideos());
        this.elements.gridToggle?.addEventListener('click', () => this.toggleGridView());
        
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.handleFilter(e));
        });
        
        this.elements.modalClose?.addEventListener('click', () => this.closeModal());
        this.elements.modalOverlay?.addEventListener('click', () => this.closeModal());
        
        this.elements.shareBtn?.addEventListener('click', () => this.shareVideo());
        this.elements.likeBtn?.addEventListener('click', () => this.likeVideo());
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.elements.videoModal.classList.contains('active')) {
                this.closeModal();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.refreshVideos();
            }
        });
    }

    async loadVideos() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/videos');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.videos = await response.json();
            this.lastUpdate = new Date();
            
            console.log(`✅ Loaded ${this.videos.length} videos`);
            
            this.applyFilters();
            this.updateStats();
            
        } catch (error) {
            console.error('❌ Error loading videos:', error);
            this.showError(error.message);
            this.videos = [];
            this.renderVideos();
        } finally {
            this.showLoading(false);
        }
    }

    applyFilters() {
        let videos = [...this.videos];
        
        if (this.searchTerm) {
            videos = videos.filter(video => 
                this.formatVideoName(video.name).toLowerCase().includes(this.searchTerm.toLowerCase()) ||
                video.name.toLowerCase().includes(this.searchTerm.toLowerCase())
            );
        }
        
        if (this.currentFilter === 'recent') {
            const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
            videos = videos.filter(v => new Date(v.modified) > oneDayAgo);
        } else if (this.currentFilter === 'hd') {
            videos = videos.filter(v => v.size > 100 * 1024 * 1024);
        } else if (this.currentFilter === 'popular') {
            videos = videos.sort((a, b) => b.size - a.size).slice(0, 8);
        }
        
        this.sortVideos(videos);
        this.filteredVideos = videos;
        this.renderVideos();
    }

    sortVideos(videos) {
        videos.sort((a, b) => {
            const aDate = new Date(a.modified);
            const bDate = new Date(b.modified);
            
            switch (this.currentSort) {
                case 'name-asc': return a.name.localeCompare(b.name);
                case 'name-desc': return b.name.localeCompare(a.name);
                case 'size-asc': return a.size - b.size;
                case 'size-desc': return b.size - a.size;
                case 'date-asc': return aDate - bDate;
                case 'date-desc':
                default: return bDate - aDate;
            }
        });
    }

    renderVideos() {
        const grid = this.elements.videoGrid;
        if (!grid) return;
        
        this.updateVideoCount();
        
        if (this.filteredVideos.length === 0) {
            grid.innerHTML = '';
            this.elements.emptyState.style.display = 'flex';
            return;
        }
        
        this.elements.emptyState.style.display = 'none';
        grid.innerHTML = this.filteredVideos.map(video => this.createVideoCard(video)).join('');
        
        document.querySelectorAll('.video-card').forEach(card => {
            card.addEventListener('click', () => {
                const videoName = card.dataset.videoName;
                const video = this.videos.find(v => v.name === videoName);
                if (video) this.openModal(video);
            });
        });
        
        // Generate thumbnails immediately for all cards
        this.generateAllThumbnailsNow();
    }

    createVideoCard(video) {
        const displayName = this.formatVideoName(video.name);
        const sizeMB = (video.size / (1024 * 1024)).toFixed(2);
        const date = this.formatDate(video.modified);
        const encodedName = video.encoded_name || encodeURIComponent(video.name);
        const videoPath = `/videos/${encodedName}`;
        const isHD = video.size > 100 * 1024 * 1024;
        
        return `
            <div class="video-card" data-video-name="${this.escapeHtml(video.name)}" data-video-path="${videoPath}">
                <div class="video-thumbnail">
                    <canvas class="video-thumb-canvas" width="400" height="225" 
                            style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;background:#1a1a1a;"></canvas>
                    <div class="play-overlay">
                        <i class="fas fa-play"></i>
                    </div>
                    ${isHD ? '<span class="video-badge">HD</span>' : ''}
                </div>
                <div class="video-info">
                    <h3 title="${this.escapeHtml(displayName)}">${this.escapeHtml(displayName)}</h3>
                    <div class="video-meta">
                        <span class="video-size">${sizeMB} MB</span>
                        <span class="video-date">
                            <i class="far fa-clock"></i>
                            ${date}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate ALL thumbnails immediately from actual video frames
     */
    async generateAllThumbnailsNow() {
        const cards = document.querySelectorAll('.video-card');
        
        console.log(`🎬 Generating thumbnails for ${cards.length} videos...`);
        
        // Process all cards in batches to avoid overwhelming the browser
        const batchSize = 3;
        for (let i = 0; i < cards.length; i += batchSize) {
            const batch = Array.from(cards).slice(i, i + batchSize);
            
            await Promise.all(batch.map(async (card, index) => {
                const canvas = card.querySelector('.video-thumb-canvas');
                const videoPath = card.dataset.videoPath;
                
                if (!canvas || !videoPath) return;
                
                // Generate thumbnail from video
                await this.generateVideoThumbnail(videoPath, canvas);
            }));
            
            // Small delay between batches
            if (i + batchSize < cards.length) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        console.log('✅ All thumbnails generated!');
    }

    /**
     * Generate actual thumbnail from video file
     */
    async generateVideoThumbnail(videoPath, canvas) {
        if (!canvas || this.processingThumbnails.has(videoPath)) {
            return;
        }
        
        // Check cache first
        if (this.thumbnailCache.has(videoPath)) {
            const ctx = canvas.getContext('2d');
            const cachedImageData = this.thumbnailCache.get(videoPath);
            ctx.putImageData(cachedImageData, 0, 0);
            return;
        }
        
        this.processingThumbnails.add(videoPath);
        
        return new Promise((resolve) => {
            const video = document.createElement('video');
            video.crossOrigin = 'anonymous';
            video.preload = 'metadata';
            video.muted = true;
            video.playsInline = true;
            
            const cleanup = () => {
                video.src = '';
                video.load();
                this.processingThumbnails.delete(videoPath);
            };
            
            const timeout = setTimeout(() => {
                console.warn('⏱️ Timeout generating thumbnail:', videoPath);
                cleanup();
                resolve(false);
            }, 15000);
            
            video.onloadedmetadata = () => {
                // Seek to 2 seconds or 10% of duration (whichever is smaller)
                const seekTime = Math.min(Math.max(video.duration * 0.1, 1), 3);
                video.currentTime = seekTime;
            };
            
            video.onseeked = () => {
                clearTimeout(timeout);
                
                try {
                    const ctx = canvas.getContext('2d');
                    
                    // Draw the video frame to canvas
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    // Cache the thumbnail
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    this.thumbnailCache.set(videoPath, imageData);
                    
                    console.log('✅ Thumbnail generated:', videoPath);
                    resolve(true);
                } catch (error) {
                    console.error('❌ Error drawing thumbnail:', error);
                    this.drawPlaceholder(canvas);
                    resolve(false);
                } finally {
                    cleanup();
                }
            };
            
            video.onerror = (e) => {
                clearTimeout(timeout);
                console.error('❌ Error loading video:', videoPath, e);
                this.drawPlaceholder(canvas);
                cleanup();
                resolve(false);
            };
            
            // Load the video
            video.src = videoPath;
            video.load();
        });
    }

    /**
     * Draw a simple placeholder if video fails to load
     */
    drawPlaceholder(canvas) {
        const ctx = canvas.getContext('2d');
        
        // Dark gradient background
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, '#1a1a1a');
        gradient.addColorStop(1, '#0d0d0d');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Orange play circle
        ctx.fillStyle = '#ff6b00';
        ctx.beginPath();
        ctx.arc(canvas.width / 2, canvas.height / 2, 40, 0, Math.PI * 2);
        ctx.fill();
        
        // White play triangle
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.moveTo(canvas.width / 2 - 15, canvas.height / 2 - 20);
        ctx.lineTo(canvas.width / 2 + 20, canvas.height / 2);
        ctx.lineTo(canvas.width / 2 - 15, canvas.height / 2 + 20);
        ctx.closePath();
        ctx.fill();
    }

    formatVideoName(name) {
        let formatted = name
            .replace(/^\d+-/, '')
            .replace(/\.[^/.]+$/, '')
            .replace(/_/g, ' ')
            .replace(/[\[\](){}]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        
        try {
            formatted = decodeURIComponent(formatted);
        } catch (e) {}
        
        return formatted || name;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
        
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: 'numeric'
        });
    }

    formatDuration(seconds) {
        if (!seconds || isNaN(seconds)) return '';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    openModal(video) {
        this.currentVideo = video;
        
        this.elements.modalTitle.textContent = this.formatVideoName(video.name);
        this.elements.modalFilename.textContent = video.name;
        this.elements.modalSize.textContent = `${(video.size / (1024 * 1024)).toFixed(2)} MB`;
        this.elements.modalDate.textContent = this.formatDate(video.modified);
        this.elements.modalResolution.textContent = 'Loading...';
        
        const videoPath = video.path || `/videos/${video.encoded_name || encodeURIComponent(video.name)}`;
        const encodedName = video.encoded_name || encodeURIComponent(video.name);
        
        this.elements.modalVideo.src = videoPath;
        this.elements.modalVideo.poster = `/api/thumbnail/${encodedName}`;
        
        this.elements.downloadBtn.href = videoPath;
        this.elements.downloadBtn.download = video.name;
        
        this.elements.modalVideo.onloadedmetadata = () => {
            const resolution = `${this.elements.modalVideo.videoWidth}x${this.elements.modalVideo.videoHeight}`;
            const duration = this.formatDuration(this.elements.modalVideo.duration);
            this.elements.modalResolution.textContent = `${resolution} • ${duration}`;
        };
        
        this.elements.modalVideo.onerror = () => {
            this.elements.modalResolution.textContent = 'Error loading video';
        };
        
        this.loadRelatedVideos(video);
        
        this.elements.videoModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.elements.videoModal.classList.remove('active');
        document.body.style.overflow = '';
        this.elements.modalVideo.pause();
        this.elements.modalVideo.src = '';
        this.currentVideo = null;
    }

    loadRelatedVideos(currentVideo) {
        const related = this.videos
            .filter(v => v.name !== currentVideo.name)
            .sort(() => Math.random() - 0.5)
            .slice(0, 4);
        
        this.elements.relatedGrid.innerHTML = related.map(video => {
            const displayName = this.formatVideoName(video.name);
            const encodedName = video.encoded_name || encodeURIComponent(video.name);
            const thumbnailUrl = `/api/thumbnail/${encodedName}`;
            
            return `
                <div class="video-card" data-video-name="${this.escapeHtml(video.name)}">
                    <div class="video-thumbnail">
                        <img src="${thumbnailUrl}" alt="${this.escapeHtml(displayName)}"
                             style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 400 225%22%3E%3Crect width=%22400%22 height=%22225%22 fill=%22%231a1a1a%22/%3E%3Ccircle cx=%22200%22 cy=%22112%22 r=%2240%22 fill=%22%23ff6b00%22/%3E%3Cpath d=%22M190 92 L220 112 L190 132 Z%22 fill=%22white%22/%3E%3C/svg%3E'">
                        <div class="play-overlay">
                            <i class="fas fa-play"></i>
                        </div>
                    </div>
                    <div class="video-info">
                        <h3 title="${this.escapeHtml(displayName)}">${this.escapeHtml(displayName)}</h3>
                    </div>
                </div>
            `;
        }).join('');
        
        this.elements.relatedGrid.querySelectorAll('.video-card').forEach(card => {
            card.addEventListener('click', () => {
                const videoName = card.dataset.videoName;
                const video = this.videos.find(v => v.name === videoName);
                if (video) {
                    this.closeModal();
                    setTimeout(() => this.openModal(video), 100);
                }
            });
        });
    }

    async shareVideo() {
        if (!this.currentVideo) return;
        
        const videoUrl = window.location.origin + 
            (this.currentVideo.path || `/videos/${encodeURIComponent(this.currentVideo.name)}`);
        
        try {
            await navigator.clipboard.writeText(videoUrl);
            this.showToast('Link copied to clipboard!');
        } catch (err) {
            this.showToast('Failed to copy link', 'error');
        }
    }

    likeVideo() {
        const icon = this.elements.likeBtn.querySelector('i');
        if (icon.classList.contains('far')) {
            icon.classList.remove('far');
            icon.classList.add('fas');
            this.showToast('Added to favorites!');
        } else {
            icon.classList.remove('fas');
            icon.classList.add('far');
            this.showToast('Removed from favorites');
        }
    }

    handleSearch(e) {
        this.searchTerm = e.target.value.trim();
        
        if (this.elements.searchClear) {
            this.elements.searchClear.style.display = this.searchTerm ? 'block' : 'none';
        }
        
        this.applyFilters();
    }

    clearSearch() {
        this.elements.searchInput.value = '';
        this.searchTerm = '';
        this.elements.searchClear.style.display = 'none';
        this.applyFilters();
    }

    handleFilter(e) {
        const tab = e.currentTarget;
        this.currentFilter = tab.dataset.filter;
        
        document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        this.applyFilters();
    }

    toggleGridView() {
        this.gridCompact = !this.gridCompact;
        
        if (this.gridCompact) {
            this.elements.videoGrid.classList.add('grid-compact');
            this.elements.gridToggle.querySelector('i').className = 'fas fa-th-large';
        } else {
            this.elements.videoGrid.classList.remove('grid-compact');
            this.elements.gridToggle.querySelector('i').className = 'fas fa-th';
        }
    }

    async refreshVideos() {
        const icon = this.elements.refreshBtn.querySelector('i');
        icon.classList.add('fa-spin');
        
        // Clear cache on refresh
        this.thumbnailCache.clear();
        
        await this.loadVideos();
        
        setTimeout(() => {
            icon.classList.remove('fa-spin');
            this.showToast('Videos refreshed!');
        }, 500);
    }

    async updateStats() {
        try {
            const response = await fetch('/api/stats');
            if (response.ok) {
                const stats = await response.json();
                this.updateStatsDisplay(stats);
                return;
            }
        } catch (error) {
            console.log('Using client-side stats');
        }
        
        this.updateClientStats();
    }

    updateStatsDisplay(stats) {
        if (this.elements.totalVideos) {
            this.elements.totalVideos.textContent = stats.total_videos || this.videos.length;
        }
        
        if (this.elements.totalSize) {
            const sizeGB = ((stats.total_size_mb || 0) / 1024).toFixed(2);
            this.elements.totalSize.textContent = `${sizeGB} GB`;
        }
        
        if (this.elements.serverPath && stats.server_info) {
            this.elements.serverPath.textContent = stats.server_info.video_folder || '/videos';
        }
        
        this.updateLastUpdateTime();
    }

    updateClientStats() {
        const totalVideos = this.videos.length;
        const totalSize = this.videos.reduce((sum, v) => sum + v.size, 0);
        const totalSizeGB = (totalSize / (1024 * 1024 * 1024)).toFixed(2);
        
        const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
        const recentCount = this.videos.filter(v => new Date(v.modified) > oneDayAgo).length;
        
        if (this.elements.totalVideos) this.elements.totalVideos.textContent = totalVideos;
        if (this.elements.totalSize) this.elements.totalSize.textContent = `${totalSizeGB} GB`;
        if (this.elements.recentVideos) this.elements.recentVideos.textContent = recentCount;
        
        this.updateLastUpdateTime();
    }

    updateLastUpdateTime() {
        const now = new Date();
        const diffMs = now - this.lastUpdate;
        const diffMins = Math.floor(diffMs / (1000 * 60));
        
        let text;
        if (diffMins < 1) text = 'Just now';
        else if (diffMins < 60) text = `${diffMins}m ago`;
        else if (diffMins < 1440) text = `${Math.floor(diffMins / 60)}h ago`;
        else text = `${Math.floor(diffMins / 1440)}d ago`;
        
        if (this.elements.lastUpdate) {
            this.elements.lastUpdate.textContent = text;
        }
    }

    updateVideoCount() {
        if (this.elements.videoCount) {
            const count = this.filteredVideos.length;
            this.elements.videoCount.textContent = `${count} video${count !== 1 ? 's' : ''}`;
        }
    }

    showLoading(show) {
        const grid = this.elements.videoGrid;
        if (!grid) return;
        
        if (show) {
            grid.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner">
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                    </div>
                    <p class="loading-text">Loading your videos...</p>
                </div>
            `;
        }
    }

    showError(message) {
        const grid = this.elements.videoGrid;
        if (!grid) return;
        
        grid.innerHTML = `
            <div class="loading-container">
                <div class="empty-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h3 class="empty-title">Error Loading Videos</h3>
                <p class="empty-text">${message}</p>
                <button class="btn-primary" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i>
                    Reload Page
                </button>
            </div>
        `;
    }

    showToast(message, type = 'success') {
        const toast = this.elements.toast;
        const toastMessage = this.elements.toastMessage;
        
        if (!toast || !toastMessage) return;
        
        toastMessage.textContent = message;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    startAutoRefresh() {
        setInterval(() => this.loadVideos(), 5 * 60 * 1000);
        setInterval(() => this.updateLastUpdateTime(), 60 * 1000);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎬 Starting XVideo Gallery...');
    window.videoGallery = new VideoGalleryApp();
});