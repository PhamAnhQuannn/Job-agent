"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";

interface Stats {
  [status: string]: number;
}

interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  status: string;
  date_applied: string | null;
  email_used: string | null;
  source_url: string | null;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({});
  const [recentApplied, setRecentApplied] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<Stats>("/api/jobs/stats").catch(() => ({})),
      api<Job[]>("/api/jobs?status=SUBMITTED&limit=10").catch(() => []),
    ]).then(([s, jobs]) => {
      setStats(s);
      setRecentApplied(jobs);
      setLoading(false);
    });
  }, []);

  const total = Object.values(stats).reduce((a, b) => a + b, 0);
  const statCards = [
    { label: "Total Jobs", value: total, color: "border-blue-500" },
    { label: "Matched", value: stats["MATCHED"] || 0, color: "border-green-500" },
    { label: "Auto-Apply", value: stats["AUTO_APPLY"] || 0, color: "border-cyan-500" },
    { label: "Submitted", value: stats["SUBMITTED"] || 0, color: "border-indigo-500" },
    { label: "Review", value: stats["REVIEW_NEEDED"] || 0, color: "border-yellow-500" },
    { label: "Failed", value: (stats["APPLY_FAILED"] || 0) + (stats["FAILED"] || 0), color: "border-red-500" },
    { label: "Interview", value: stats["INTERVIEW"] || 0, color: "border-emerald-500" },
    { label: "Offer", value: stats["OFFER"] || 0, color: "border-teal-500" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {statCards.map((card) => (
              <div
                key={card.label}
                className={`bg-white rounded-lg shadow p-4 border-l-4 ${card.color}`}
              >
                <div className="text-xs font-semibold uppercase text-gray-500">
                  {card.label}
                </div>
                <div className="text-3xl font-bold mt-1">{card.value}</div>
              </div>
            ))}
          </div>

          {/* Recent Submissions */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">
                Recent Applications
              </h2>
              <Link
                href="/applied"
                className="text-xs text-blue-600 hover:underline"
              >
                View All →
              </Link>
            </div>
            {recentApplied.length === 0 ? (
              <p className="p-4 text-sm text-gray-500">No applications yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                  <tr>
                    <th className="px-4 py-2">Company</th>
                    <th className="px-4 py-2">Position</th>
                    <th className="px-4 py-2">Email Used</th>
                    <th className="px-4 py-2">Applied</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {recentApplied.map((job) => (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <Link
                          href={`/jobs/${job.id}`}
                          className="text-blue-600 hover:underline font-medium"
                        >
                          {job.company}
                        </Link>
                      </td>
                      <td className="px-4 py-2">{job.title}</td>
                      <td className="px-4 py-2 text-xs font-mono text-gray-600">
                        {job.email_used || "—"}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {job.date_applied
                          ? new Date(job.date_applied).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
