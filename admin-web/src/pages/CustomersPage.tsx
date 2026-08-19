import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { ShieldCheck, UserCheck, Lock, UserPlus } from "lucide-react";

interface CustomerUser {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  role: string;
  status: string;
}

export function CustomersPage() {
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<CustomerUser[]>([]);
  const [lockers, setLockers] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      api.get("/api/v1/admin/customers"),
      api.get("/api/v1/admin/lockers"),
    ]).then(([custRes, lockerRes]) => {
      setCustomers(custRes.data.data);
      setLockers(lockerRes.data.data);
    });
  }, []);

  const filtered = customers.filter(
    (c) =>
      !search ||
      c.full_name.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      c.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-primary">Registered Customers</h1>
          <p className="text-sm text-slate-500">
            Customers authorized with biometric facial embeddings registered in Project NPN.
          </p>
        </div>

        <Link
          to="/enrollment"
          className="btn-primary px-4 py-2 text-xs font-semibold flex items-center gap-2 shadow-sm rounded-lg"
        >
          <UserPlus size={15} />
          <span>+ Enroll New Customer</span>
        </Link>
      </div>


      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by customer name, email, or ID..."
        className="text-sm border border-border rounded-lg px-3.5 py-2 w-96 max-w-full shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
      />

      <div className="card overflow-hidden shadow-sm rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-xs text-slate-500">
              <th className="py-3 px-4 font-semibold">Customer ID</th>
              <th className="font-semibold">Full Name</th>
              <th className="font-semibold">Email &amp; Phone</th>
              <th className="font-semibold">Assigned Locker</th>
              <th className="font-semibold">Face Recognition Status</th>
              <th className="font-semibold">Account Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((c) => {
              const assignedLocker = lockers.find((l) => l.customer_id === c.id);
              return (
                <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs font-semibold text-primary">{c.id}</td>
                  <td className="font-medium text-slate-800 flex items-center gap-2 py-3">
                    <div className="w-7 h-7 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-xs">
                      {c.full_name.slice(-3)}
                    </div>
                    {c.full_name}
                  </td>
                  <td className="text-xs text-slate-600">
                    <div>{c.email}</div>
                    <div className="text-slate-400 font-mono">{c.phone}</div>
                  </td>
                  <td className="font-mono text-xs">
                    {assignedLocker ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-800 rounded font-semibold border border-slate-200">
                        <Lock size={12} className="text-slate-500" />
                        {assignedLocker.locker_number} ({assignedLocker.locker_size})
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-xs font-semibold">
                      <ShieldCheck size={13} />
                      Project NPN Active
                    </span>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                      <UserCheck size={12} />
                      {c.status}
                    </span>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400 text-xs">
                  No customers found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
