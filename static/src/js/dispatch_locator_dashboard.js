/** @odoo-module **/

import { Component, useState, onMounted, onWillDestroy, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DispatchLocatorDashboard extends Component {
    static template = "brandix_dispatch_locator.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchInput = useRef("searchInput");

        const now = new Date();
        this.state = useState({
            currentTime: this.formatTime(now),
            currentDate: this.formatDate(now),
            activeTab: "search", // 'search' | 'racks'
            searchTerm: "",
            loading: false,
            showKeypad: false,
            searchResult: null,
            warehouseRacks: [],
            // Movement History Modal
            historyModalOpen: false,
            currentHistoryParcelName: "",
            parcelHistoryLogs: [],
            // Relocate Rack Modal
            relocateModalOpen: false,
            relocateParcelId: null,
            relocateParcelName: "",
            selectedNewLocationId: "",
            relocateReason: "",
        });

        this.clockTimer = null;

        onMounted(() => {
            this.startClock();
            this.loadWarehouseRacks();
            if (this.searchInput.el) {
                this.searchInput.el.focus();
            }
        });

        onWillDestroy(() => {
            this.stopClock();
        });
    }

    startClock() {
        this.clockTimer = setInterval(() => {
            const now = new Date();
            this.state.currentTime = this.formatTime(now);
            this.state.currentDate = this.formatDate(now);
        }, 1000);
    }

    stopClock() {
        if (this.clockTimer) {
            clearInterval(this.clockTimer);
            this.clockTimer = null;
        }
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    formatDate(date) {
        return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
    }

    switchTab(tab) {
        this.state.activeTab = tab;
        if (tab === "racks") {
            this.loadWarehouseRacks();
        }
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen().catch(() => {});
            }
        }
    }

    async refreshData() {
        if (this.state.searchTerm.trim()) {
            await this.executeSearch();
        }
        await this.loadWarehouseRacks();
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
    }

    onSearchKeyDown(ev) {
        if (ev.key === "Enter") {
            this.executeSearch();
        }
    }

    clearSearch() {
        this.state.searchTerm = "";
        this.state.searchResult = null;
        if (this.searchInput.el) {
            this.searchInput.el.focus();
        }
    }

    quickSearch(term) {
        this.state.searchTerm = term;
        this.executeSearch();
    }

    toggleOnScreenKeypad() {
        this.state.showKeypad = !this.state.showKeypad;
    }

    pressKey(k) {
        if (k === "BACKSPACE") {
            this.state.searchTerm = this.state.searchTerm.slice(0, -1);
        } else {
            this.state.searchTerm += k;
        }
        if (this.searchInput.el) {
            this.searchInput.el.focus();
        }
    }

    async executeSearch() {
        const query = this.state.searchTerm.trim();
        if (!query) {
            this.notification.add("Please enter a Docket No, Schedule No, or Rack to search.", { type: "warning" });
            return;
        }

        this.state.loading = true;
        this.state.activeTab = "search";
        try {
            const result = await this.orm.call(
                "brandix.dispatch.locator",
                "search_dispatch_data",
                [query]
            );
            this.state.searchResult = result;
        } catch (error) {
            console.error("Dispatch locator search failed:", error);
            this.notification.add("Failed to retrieve dispatch data. Please try again.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async loadWarehouseRacks() {
        try {
            const racks = await this.orm.call(
                "brandix.dispatch.locator",
                "get_warehouse_racks_overview",
                []
            );
            this.state.warehouseRacks = racks;
        } catch (error) {
            console.error("Failed to load warehouse racks:", error);
        }
    }

    async openParcelHistory(parcelId, parcelName) {
        this.state.currentHistoryParcelName = parcelName;
        this.state.historyModalOpen = true;
        this.state.parcelHistoryLogs = [];
        try {
            const logs = await this.orm.call(
                "brandix.dispatch.locator",
                "get_parcel_location_history",
                [parcelId]
            );
            this.state.parcelHistoryLogs = logs;
        } catch (error) {
            console.error("Failed to load parcel location history:", error);
            this.notification.add("Failed to fetch location history.", { type: "danger" });
        }
    }

    closeHistoryModal() {
        this.state.historyModalOpen = false;
        this.state.parcelHistoryLogs = [];
    }

    openRelocateModal(parcelId, parcelName, currentLocationId) {
        this.state.relocateParcelId = parcelId;
        this.state.relocateParcelName = parcelName;
        this.state.selectedNewLocationId = currentLocationId ? String(currentLocationId) : "";
        this.state.relocateReason = "";
        this.state.relocateModalOpen = true;
    }

    closeRelocateModal() {
        this.state.relocateModalOpen = false;
        this.state.relocateParcelId = null;
    }

    async confirmRelocate() {
        if (!this.state.selectedNewLocationId) {
            this.notification.add("Please select a target Rack / Bin.", { type: "warning" });
            return;
        }

        const newLocId = parseInt(this.state.selectedNewLocationId, 10);
        try {
            const res = await this.orm.call(
                "brandix.dispatch.locator",
                "reassign_parcel_location",
                [this.state.relocateParcelId, newLocId, this.state.relocateReason]
            );
            if (res && res.success) {
                this.notification.add(`Parcel moved to ${res.new_location_name} successfully!`, { type: "success" });
                this.closeRelocateModal();
                // Refresh active search and racks
                if (this.state.searchTerm.trim()) {
                    await this.executeSearch();
                }
                await this.loadWarehouseRacks();
            } else {
                this.notification.add((res && res.error) || "Relocation failed.", { type: "danger" });
            }
        } catch (error) {
            console.error("Relocation error:", error);
            this.notification.add("Error reassigning parcel location.", { type: "danger" });
        }
    }
}

registry.category("actions").add("brandix_dispatch_locator_dashboard", DispatchLocatorDashboard);
