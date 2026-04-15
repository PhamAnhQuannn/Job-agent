"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";

interface DailyStat {
  date: string;
  jobs_found: number;
  auto_applied: number;
  review_queued: number;
  skipped: number;
  duplicates: number;
  failed: number;
  responses: number;
}

interface Stats {
  [status: string]: number;
}

export default function ExportPage() {
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<DailyStat[]>("/api/export/stats"),
      api<Stats>("/api/jobs/stats"),
    ])
      .then(([d, s]) => {
        setDaily(d);
        setStats(s);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Reports</h1>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold mb-3">Current Totals</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(stats).map(([status, count]) => (
            <div key={status} className="text-sm">
              <span className="text-gray-500">{status}: </span>
              <span className="font-semibold">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-3">Daily History</h2>
        {daily.length === 0 ? (
          <p className="text-gray-500">No daily stats yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Found</th>
                  <th className="px-3 py-2">Applied</th>
                  <th className="px-3 py-2">Review</th>
                  <th className="px-3 py-2">Skipped</th>
                  <th className="px-3 py-2">Dupes</th>
                  <th className="px-3 py-2">Failed</th>
                  <th className="px-3 py-2">Responses</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {daily.map((row) => (
                  <tr key={row.date}>
                    <td className="px-3 py-2 font-medium">{row.date}</td>
                    <td className="px-3 py-2">{row.jobs_found}</td>
                    <td className="px-3 py-2">{row.auto_applied}</td>
                    <td className="px-3 py-2">{row.review_queued}</td>
                    <td className="px-3 py-2">{row.skipped}</td>
                    <td className="px-3 py-2">{row.duplicates}</td>
                    <td className="px-3 py-2">{row.failed}</td>
                    <td className="px-3 py-2">{row.responses}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
