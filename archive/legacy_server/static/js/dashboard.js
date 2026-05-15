class Dashboard {
    constructor() {
        this.stats = {
            clients_connected: 0,
            active_tunnels: 0,
            active_connections: 0,
            bytes_transferred: 0
        };
        
        this.loadStats();
        setInterval(() => this.loadStats(), 5000); // Обновление каждые 5 секунд
    }

    // Загрузка статистики
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) throw new Error('Failed to load stats');
            
            this.stats = await response.json();
            this.updateStatsDisplay();
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    // Обновление отображения статистики
    updateStatsDisplay() {
        // Обновляем числа
        document.getElementById('clientCount').textContent = this.stats.clients_connected;
        document.getElementById('tunnelCount').textContent = this.stats.active_tunnels;
        document.getElementById('connectionCount').textContent = this.stats.active_connections;
        document.getElementById('dataTransferred').textContent = app.formatBytes(this.stats.bytes_transferred);

        // Добавляем анимацию
        this.animateValue('clientCount', this.stats.clients_connected);
        this.animateValue('tunnelCount', this.stats.active_tunnels);
        this.animateValue('connectionCount', this.stats.active_connections);
    }

    // Анимация изменения чисел
    animateValue(elementId, newValue) {
        const element = document.getElementById(elementId);
        const currentValue = parseInt(element.textContent) || 0;
        
        if (currentValue === newValue) return;

        let start = null;
        const duration = 500; // milliseconds

        const step = (timestamp) => {
            if (!start) start = timestamp;
            const progress = Math.min((timestamp - start) / duration, 1);
            
            const value = Math.floor(progress * (newValue - currentValue) + currentValue);
            element.textContent = value;
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        
        window.requestAnimationFrame(step);
    }
}

// Инициализация дашборда при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});

// Глобальная функция для ручного обновления
function loadStats() {
    if (window.dashboard) {
        window.dashboard.loadStats();
        app.showAlert('Stats refreshed!', 'success');
    }
}