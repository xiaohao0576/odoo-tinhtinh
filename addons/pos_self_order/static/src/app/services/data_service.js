import { PosData } from "@point_of_sale/app/services/data_service";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";
import { registerPythonTemplate } from "@point_of_sale/app/utils/convert_python_template";

export const unpatchSelf = patch(PosData.prototype, {
    async loadInitialData() {
        const configId = session.data.config_id;
        const localData = await this.getCachedServerDataFromIndexedDB();
        const localPartners = localData?.["res.partner"] || [];
        const localPrinters = localData?.["pos.printer"] || [];
        const serverPartners = [];
        const serverPrinters = [];
        if (session.data.locked_partner) {
            serverPartners.push(session.data.locked_partner);
        }
        if (session.data.locked_printer) {
            serverPrinters.push(session.data.locked_printer);
        }
        await this.fetchReceiptTemplate();
        const data = await rpc(`/pos-self/data/${parseInt(configId)}`, {
            access_token: odoo.access_token,
        });
        const mergedPartners = [...(data["res.partner"] || []), ...localPartners, ...serverPartners];
        const mergedPrinters = [...(data["pos.printer"] || []), ...localPrinters, ...serverPrinters];
        data["res.partner"] = Array.from(
            new Map(mergedPartners.filter((partner) => partner?.id).map((partner) => [partner.id, partner])).values()
        );
        data["pos.printer"] = Array.from(
            new Map(mergedPrinters.filter((printer) => printer?.id).map((printer) => [printer.id, printer])).values()
        );
        return data;
    },
    async fetchReceiptTemplate() {
        const configId = session.data.config_id;
        const data = await rpc(`/pos-self/receipt-template/${parseInt(configId)}`);
        for (const [name, string] of data) {
            registerPythonTemplate(name, "", string);
        }
    },
    async loadFieldsAndRelations() {
        const configId = session.data.config_id;
        return await rpc(`/pos-self/relations/${parseInt(configId)}`);
    },
    get databaseName() {
        return `pos-self-order-${odoo.access_token}`;
    },
    async initializeDeviceIdentifier() {
        return false;
    },
    initIndexedDB() {
        return session.data.self_ordering_mode === "mobile"
            ? super.initIndexedDB(...arguments)
            : true;
    },
    initListeners() {
        return session.data.self_ordering_mode === "mobile"
            ? super.initListeners(...arguments)
            : true;
    },
    synchronizeLocalDataInIndexedDB() {
        return session.data.self_ordering_mode === "mobile"
            ? super.synchronizeLocalDataInIndexedDB(...arguments)
            : true;
    },
    synchronizeServerDataInIndexedDB() {
        return session.data.self_ordering_mode === "mobile"
            ? super.synchronizeServerDataInIndexedDB(...arguments)
            : true;
    },
    async getCachedServerDataFromIndexedDB() {
        return session.data.self_ordering_mode === "mobile"
            ? await super.getCachedServerDataFromIndexedDB(...arguments)
            : {};
    },
    async getLocalDataFromIndexedDB() {
        return session.data.self_ordering_mode === "mobile"
            ? await super.getLocalDataFromIndexedDB(...arguments)
            : {};
    },
    async missingRecursive(recordMap) {
        return recordMap;
    },
    async checkAndDeleteMissingOrders(results) {},
    async deleteRecordsInIndexedDB(model, ids) {
        return session.data.self_ordering_mode === "mobile"
            ? await super.deleteRecordsInIndexedDB(...arguments)
            : true;
    },
});
