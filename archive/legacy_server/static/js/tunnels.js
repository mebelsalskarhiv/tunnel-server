class TunnelsManager {
    constructor() {
        this.tunnels = [];
        this.clients = [];
        this.loadTunnels();
        this.loadClients();
    }

    // Загрузка списка туннелей
    async loadTunnels() {
        try {
            const response = await fetch('/api/tunnels');
            if (!response.ok) throw new Error('Failed to load tunnels');
            
            this.tunnels = await response.json();
            this.renderTunnelsTable();
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Загрузка списка клиентов для выпадающего списка
    async loadClients() {
        try {
            const response = await fetch('/api/clients');
            if (!response.ok) throw new Error('Failed to load clients');
            
            this.clients = await response.json();
            this.renderClientSelect();
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Отрисовка таблицы туннелей
    renderTunnelsTable() {
        const tbody = document.getElementById('tunnelsTableBody');
        
        if (this.tunnels.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center text-muted py-4">
                        <i class="bi bi-diagram-3 fs-1 d-block mb-2"></i>
                        No tunnels found. Create your first tunnel above.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.tunnels.map(tunnel => `
            <tr class="fade-in">
                <td>
                    <strong>${this.escapeHtml(tunnel.subdomain)}</strong>
                </td>
                <td>
                    <a href="http://${tunnel.public_url}" target="_blank" class="text-decoration-none">
                        ${tunnel.public_url}
                        <i class="bi bi-box-arrow-up-right ms-1 small"></i>
                    </a>
                </td>
                <td>${this.escapeHtml(tunnel.client_name)}</td>
                <td>
                    <code class="text-muted">${tunnel.local_host}:${tunnel.local_port}</code>
                </td>
                <td>
                    <span class="badge bg-info">${tunnel.protocol.toUpperCase()}</span>
                </td>
                <td>
                    <span class="status-badge ${tunnel.is_active ? 'status-active' : 'status-inactive'}">
                        <i class="bi ${tunnel.is_active ? 'bi-check-circle' : 'bi-x-circle'} me-1"></i>
                        ${tunnel.is_active ? 'Active' : 'Inactive'}
                    </span>
                </td>
                <td>
                    <small class="text-muted">${new Date(tunnel.created_at).toLocaleString()}</small>
                </td>
                <td>
                    <button class="btn btn-outline-danger btn-sm" 
                            onclick="tunnelsManager.deleteTunnel('${tunnel.id}')"
                            title="Delete tunnel">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // Отрисовка выпадающего списка клиентов
    renderClientSelect() {
        const select = document.getElementById('tunnelClient');
        select.innerHTML = '<option value="">Select a client...</option>';
        
        this.clients.forEach(client => {
            const option = document.createElement('option');
            option.value = client.id;
            option.textContent = `${client.name} (${client.tunnel_count}/${client.max_tunnels} tunnels)`;
            select.appendChild(option);
        });
    }

    // Создание туннеля
    async createTunnel() {
        const clientId = document.getElementById('tunnelClient').value;
        const subdomain = document.getElementById('tunnelSubdomain').value.trim();
        const localHost = document.getElementById('tunnelLocalHost').value.trim();
        const localPort = parseInt(document.getElementById('tunnelLocalPort').value);
        const protocol = document.getElementById('tunnelProtocol').value;

        // Валидация
        if (!clientId) {
            app.showAlert('Please select a client', 'warning');
            return;
        }
        if (!subdomain) {
            app.showAlert('Please enter a subdomain', 'warning');
            return;
        }
        if (!localHost) {
            app.showAlert('Please enter local host', 'warning');
            return;
        }
        if (!localPort || localPort < 1 || localPort > 65535) {
            app.showAlert('Please enter a valid local port (1-65535)', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/tunnels', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_id: clientId,
                    subdomain: subdomain,
                    local_host: localHost,
                    local_port: localPort,
                    protocol: protocol
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                app.showAlert('Tunnel created successfully!', 'success');
                
                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('createTunnelModal'));
                modal.hide();
                
                // Сбрасываем форму
                document.getElementById('createTunnelForm').reset();
                
                // Обновляем списки
                await this.loadTunnels();
                await this.loadClients();
            } else {
                app.showAlert(result.message || 'Failed to create tunnel', 'error');
            }
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Удаление туннеля
    async deleteTunnel(tunnelId) {
        const tunnel = this.tunnels.find(t => t.id === tunnelId);
        if (!tunnel) return;

        if (!confirm(`Are you sure you want to delete tunnel "${tunnel.subdomain}.${tunnel.public_url.split('.')[1]}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/tunnels/${tunnelId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.status === 'success') {
                app.showAlert('Tunnel deleted successfully!', 'success');
                await this.loadTunnels();
                await this.loadClients();
            } else {
                app.showAlert(result.message || 'Failed to delete tunnel', 'error');
            }
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Экранирование HTML
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Глобальный экземпляр менеджера туннелей
window.tunnelsManager = new TunnelsManager();

// Функции для глобальной области видимости
function createTunnel() {
    tunnelsManager.createTunnel();
}