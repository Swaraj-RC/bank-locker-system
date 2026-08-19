import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../services/api";
import { LockerRequest, Locker, AuthUser } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { Lock, User, PlusCircle, ShieldCheck, ArrowRight, X } from "lucide-react";

const STATUS_FILTERS = [
  "", "SUBMITTED", "APPROVED", "ACCESS_ACTIVE", "COMPLETED",
  "MANUAL_REVIEW", "BLOCKED", "REJECTED", "CANCELLED",
];

export function RequestsPage() {
  const [requests, setRequests] = useState<LockerRequest[]>([]);
  const [status, setStatus] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [occupiedLockers, setOccupiedLockers] = useState<Locker[]>([]);
  const [selectedLockerId, setSelectedLockerId] = useState("");
  const [requestType, setRequestType] = useState("ACCESS");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function load() {
    const params = status ? { status } : {};
    const [resp, lockersResp] = await Promise.all([
      api.get("/api/v1/admin/requests", { params }),
      api.get("/api/v1/admin/lockers"),
    ]);
    setRequests(resp.data.data);
    const occupied = (lockersResp.data?.data || []).filter(
      (l: Locker) => l.customer_id !== null
    );
    setOccupiedLockers(occupied);
    if (occupied.length > 0 && !selectedLockerId) {
      setSelectedLockerId(occupied[0].id);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function handleCreateRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedLockerId) return;
    setCreating(true);
    setCreateError(null);
    try {
      await api.post("/api/v1/admin/requests", {
        locker_id: selectedLockerId,
        request_type: requestType,
      });
      setShowCreateModal(false);
      await load();
    } catch (err) {
      setCreateError(apiErrorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-primary">Locker Access Requests</h1>
          <p className="text-sm text-slate-500">
            Real-time queue of customer access requests pending biometric face verification.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="text-xs font-medium border border-border rounded-lg px-3 py-2 bg-surface shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>
                {s ? s.replace(/_/g, " ") : "All Request Statuses"}
              </option>
            ))}
          </select>

          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary text-xs px-3.5 py-2 flex items-center gap-1.5 shadow-sm rounded-lg"
          >
            <PlusCircle size={15} />
            <span>New Access Request</span>
          </button>
        </div>
      </div>

      <div className="card overflow-hidden shadow-sm rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-xs text-slate-500">
              <th className="py-3 px-4 font-semibold">Request ID</th>
              <th className="font-semibold">Customer</th>
              <th className="font-semibold">Locker</th>
              <th className="font-semibold">Type</th>
              <th className="font-semibold">Status</th>
              <th className="font-semibold">Submitted At</th>
              <th className="font-semibold px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {requests.map((r) => {
              const isSubmitted = r.status === "SUBMITTED";
              return (
                <tr key={r.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs font-semibold text-slate-600">
                    {r.id.slice(0, 8)}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold font-mono">
                        {r.customer_id.slice(-2)}
                      </div>
                      <div>
                        <div className="font-mono text-xs font-bold text-primary">{r.customer_id}</div>
                        {r.customer_name && (
                          <div className="text-[11px] text-slate-500">{r.customer_name}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      <Lock size={11} className="text-slate-500" />
                      {r.locker_number || r.locker_id.slice(0, 6)}
                    </span>
                  </td>
                  <td className="text-xs font-medium text-slate-600">{r.request_type}</td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="text-slate-500 text-xs font-mono">
                    {new Date(r.requested_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </td>
                  <td className="px-4 text-right">
                    <Link
                      to={`/requests/${r.id}`}
                      className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-md transition-colors ${
                        isSubmitted
                          ? "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm"
                          : "text-primary hover:bg-slate-100"
                      }`}
                    >
                      {isSubmitted ? (
                        <>
                          <ShieldCheck size={13} /> Verify Face →
                        </>
                      ) : (
                        <>
                          Open <ArrowRight size={12} />
                        </>
                      )}
                    </Link>
                  </td>
                </tr>
              );
            })}
            {requests.length === 0 && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-slate-400 text-xs">
                  No requests found matching this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal to create a new access request for existing customer locker */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface rounded-2xl border border-border shadow-xl max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h2 className="text-base font-bold text-primary flex items-center gap-2">
                <PlusCircle size={18} className="text-blue-600" /> Create Locker Access Request
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateRequest} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Select Customer's Assigned Locker <span className="text-red-500">*</span>
                </label>
                <select
                  required
                  value={selectedLockerId}
                  onChange={(e) => setSelectedLockerId(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:outline-none"
                >
                  {occupiedLockers.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.locker_number} ({l.locker_size}) — Assigned to Customer {l.customer_id}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Request Type
                </label>
                <select
                  value={requestType}
                  onChange={(e) => setRequestType(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:outline-none"
                >
                  <option value="ACCESS">ACCESS (Customer Locker Operation)</option>
                  <option value="INSPECTION">INSPECTION</option>
                  <option value="MAINTENANCE">MAINTENANCE</option>
                </select>
              </div>

              {createError && (
                <div className="p-2.5 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200">
                  {createError}
                </div>
              )}

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !selectedLockerId}
                  className="btn-primary text-xs px-4 py-2 font-semibold flex items-center gap-2"
                >
                  {creating ? "Submitting Request…" : "Submit Access Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

