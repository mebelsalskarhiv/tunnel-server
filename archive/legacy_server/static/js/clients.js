class ClientsManager {
    constructor() {
        this.clients = [];
        this.currentClientId = null;
        this.loadClients();
    }

    // Загрузка списка клиентов
    async loadClients() {
        try {
            const response = await fetch('/api/clients');
            if (!response.ok) throw new Error('Failed to load clients');
            
            this.clients = await response.json();
            this.renderClientsTable();
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Отрисовка таблицы клиентов
    renderClientsTable() {
        const tbody = document.getElementById('clientsTableBody');
        
        if (this.clients.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted py-4">
                        <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                        No clients found. Create your first client above.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.clients.map(client => `
            <tr class="fade-in">
                <td>
                    <strong>${this.escapeHtml(client.name)}</strong>
                </td>
                <td>
                    <code class="text-muted">${client.id}</code>
                </td>
                <td>
                    <span class="status-badge ${client.is_connected ? 'status-active' : 'status-inactive'}">
                        <i class="bi ${client.is_connected ? 'bi-check-circle' : 'bi-x-circle'} me-1"></i>
                        ${client.is_connected ? 'Connected' : 'Disconnected'}
                    </span>
                </td>
                <td>
                    <span class="badge bg-secondary">${client.tunnel_count}/${client.max_tunnels}</span>
                </td>
                <td>
                    <small class="text-muted">${new Date(client.created_at).toLocaleString()}</small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="clientsManager.showConfig('${client.id}')"
                                title="Get configuration">
                            <i class="bi bi-gear"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="clientsManager.deleteClient('${client.id}')"
                                title="Delete client">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // Создание клиента
    async createClient() {
        const name = document.getElementById('clientName').value.trim();
        const maxTunnels = parseInt(document.getElementById('maxTunnels').value);

        if (!name) {
            app.showAlert('Please enter a client name', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/clients', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    max_tunnels: maxTunnels
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                app.showAlert('Client created successfully!', 'success');
                
                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('createClientModal'));
                modal.hide();
                
                // Сбрасываем форму
                document.getElementById('createClientForm').reset();
                
                // Обновляем список клиентов
                await this.loadClients();
            } else {
                app.showAlert(result.message || 'Failed to create client', 'error');
            }
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Показ конфигурации клиента
    async showConfig(clientId) {
        try {
            const response = await fetch(`/api/clients/${clientId}/config`);
            if (!response.ok) throw new Error('Failed to load config');
            
            const config = await response.json();
            this.currentClientId = clientId;
            
            // Форматируем JSON для красивого отображения
            const configContent = document.getElementById('configContent');
            configContent.textContent = JSON.stringify(config, null, 2);
            
            // Показываем модальное окно
            const modal = new bootstrap.Modal(document.getElementById('configModal'));
            modal.show();
        } catch (error) {
            app.handleApiError(error);
        }
    }

    // Скачивание конфигурации
    downloadConfig() {
        if (!this.currentClientId) return;
        
        const configContent = document.getElementById('configContent').textContent;
        const blob = new Blob([configContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tunnel-config-${this.currentClientId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        app.showAlert('Configuration downloaded successfully!', 'success');
    }

    // Удаление клиента
    async deleteClient(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        if (!confirm(`Are you sure you want to delete client "${client.name}"? This will also delete all associated tunnels.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/clients/${clientId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.status === 'success') {
                app.showAlert('Client deleted successfully!', 'success');
                await this.loadClients();
            } else {
                app.showAlert(result.message || 'Failed to delete client', 'error');
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

// Глобальный экземпляр менеджера клиентов
window.clientsManager = new ClientsManager();

// Функции для глобальной области видимости
function createClient() {
    clientsManager.createClient();
}