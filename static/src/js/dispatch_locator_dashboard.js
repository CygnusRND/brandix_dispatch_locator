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
            // Live Status
            lastSyncedTime: this.formatTime(now),
        });

        this.clockTimer = null;
        this.autoRefreshTimer = null;
        this.inactivityTimer = null;
        this.INACTIVITY_TIMEOUT_MS = 2 * 60 * 1000; // 2 minutes (120,000 ms)

        this.boundHandleActivity = this.handleUserActivity.bind(this);
        this.interactionEvents = ['mousedown', 'mousemove', 'keydown', 'touchstart', 'scroll', 'click'];

        onMounted(() => {
            this.startClock();
            this.startAutoRefresh();
            this.startInactivityMonitoring();
            this.loadWarehouseRacks();
            if (this.searchInput.el) {
                this.searchInput.el.focus();
            }
        });

        onWillDestroy(() => {
            this.stopClock();
            this.stopAutoRefresh();
            this.stopInactivityMonitoring();
        });
    }

    /* ----------------------------------------------------
       CLOCK & LIVE AUTO-REFRESH (SMART BOARD REAL-TIME)
       ---------------------------------------------------- */
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

    startAutoRefresh() {
        // Automatically re-syncs active view every 15 seconds without browser refresh
        this.autoRefreshTimer = setInterval(() => {
            this.autoSyncDashboard();
        }, 15000);
    }

    stopAutoRefresh() {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    async autoSyncDashboard() {
        // Do not auto-sync if modals are actively open
        if (this.state.historyModalOpen || this.state.relocateModalOpen) {
            return;
        }

        try {
            if (this.state.searchTerm.trim() && this.state.searchResult) {
                // Background refresh of search data without triggering loading spinner
                const result = await this.orm.call(
                    "brandix.dispatch.locator",
                    "search_dispatch_data",
                    [this.state.searchTerm.trim()]
                );
                if (result && result.status !== 'error') {
                    this.state.searchResult = result;
                }
            }

            if (this.state.activeTab === "racks") {
                await this.loadWarehouseRacks();
            }

            this.state.lastSyncedTime = this.formatTime(new Date());
        } catch (error) {
            console.warn("Background auto-sync skipped:", error);
        }
    }

    /* ----------------------------------------------------
       INACTIVITY AUTO-TIMEOUT (RESET AFTER 2 MINUTES)
       ---------------------------------------------------- */
    startInactivityMonitoring() {
        this.interactionEvents.forEach(ev => {
            window.addEventListener(ev, this.boundHandleActivity, { passive: true });
        });
        this.resetInactivityTimer();
    }

    stopInactivityMonitoring() {
        this.interactionEvents.forEach(ev => {
            window.removeEventListener(ev, this.boundHandleActivity);
        });
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
            this.inactivityTimer = null;
        }
    }

    handleUserActivity() {
        this.resetInactivityTimer();
    }

    resetInactivityTimer() {
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
            this.inactivityTimer = null;
        }
        this.inactivityTimer = setTimeout(() => {
            this.onInactivityTimeout();
        }, this.INACTIVITY_TIMEOUT_MS);
    }

    onInactivityTimeout() {
        // If a search result is open or non-default state exists, reset back to base view
        if (this.state.searchTerm || this.state.searchResult || this.state.historyModalOpen || this.state.relocateModalOpen || this.state.activeTab !== 'search') {
            this.closeHistoryModal();
            this.closeRelocateModal();
            this.state.showKeypad = false;
            this.state.activeTab = "search";
            this.clearSearch();
            this.loadWarehouseRacks();
        }
    }

    /* ----------------------------------------------------
       HELPERS & UI ACTIONS
       ---------------------------------------------------- */
    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    formatDate(date) {
        return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
    }

    formatText(val) {
        if (!val && val !== 0) return "-";
        if (typeof val === "object") {
            return val.en_US || Object.values(val)[0] || "-";
        }
        return String(val);
    }

    switchTab(tab) {
        this.resetInactivityTimer();
        this.state.activeTab = tab;
        if (tab === "racks") {
            this.loadWarehouseRacks();
        }
    }

    toggleFullscreen() {
        this.resetInactivityTimer();
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen().catch(() => {});
            }
        }
    }

    async refreshData() {
        this.resetInactivityTimer();
        if (this.state.searchTerm.trim()) {
            await this.executeSearch();
        }
        await this.loadWarehouseRacks();
        this.state.lastSyncedTime = this.formatTime(new Date());
    }

    onSearchInput(ev) {
        this.resetInactivityTimer();
        this.state.searchTerm = ev.target.value;
    }

    onSearchKeyDown(ev) {
        this.resetInactivityTimer();
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
        this.resetInactivityTimer();
        this.state.searchTerm = term;
        this.executeSearch();
    }

    toggleOnScreenKeypad() {
        this.resetInactivityTimer();
        this.state.showKeypad = !this.state.showKeypad;
    }

    pressKey(k) {
        this.resetInactivityTimer();
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
        this.resetInactivityTimer();
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
            this.state.lastSyncedTime = this.formatTime(new Date());
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

    async openParcelHistory(parcelId, parcelName, parcelType = 'cut') {
        this.resetInactivityTimer();
        this.state.currentHistoryParcelName = parcelName;
        this.state.historyModalOpen = true;
        this.state.parcelHistoryLogs = [];
        try {
            const logs = await this.orm.call(
                "brandix.dispatch.locator",
                "get_parcel_location_history",
                [parcelId, parcelType]
            );
            this.state.parcelHistoryLogs = logs;
        } catch (error) {
            console.error("Failed to load parcel location history:", error);
            this.notification.add("Failed to fetch location history.", { type: "danger" });
        }
    }

    closeHistoryModal() {
        this.resetInactivityTimer();
        this.state.historyModalOpen = false;
        this.state.parcelHistoryLogs = [];
    }

    openRelocateModal(parcelId, parcelName, currentLocationId, parcelType = 'cut') {
        this.resetInactivityTimer();
        this.state.relocateParcelId = parcelId;
        this.state.relocateParcelName = parcelName;
        this.state.relocateParcelType = parcelType;
        this.state.selectedNewLocationId = currentLocationId ? String(currentLocationId) : "";
        this.state.relocateReason = "";
        this.state.relocateModalOpen = true;
    }

    closeRelocateModal() {
        this.resetInactivityTimer();
        this.state.relocateModalOpen = false;
        this.state.relocateParcelId = null;
        this.state.relocateParcelType = 'cut';
    }

    async confirmRelocate() {
        this.resetInactivityTimer();
        if (!this.state.selectedNewLocationId) {
            this.notification.add("Please select a target Rack / Bin.", { type: "warning" });
            return;
        }

        const newLocId = parseInt(this.state.selectedNewLocationId, 10);
        try {
            const res = await this.orm.call(
                "brandix.dispatch.locator",
                "reassign_parcel_location",
                [this.state.relocateParcelId, newLocId, this.state.relocateReason, this.state.relocateParcelType || 'cut']
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
