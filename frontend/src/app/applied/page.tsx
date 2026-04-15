"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  source: string | null;
  source_url: string | null;
  status: string;
  date_applied: string | null;
  email_used: string | null;
  screenshot_path: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  SUBMITTED: "bg-purple-100 text-purple-700",
  INTERVIEW: "bg-emerald-100 text-emerald-700",
  OFFER: "bg-teal-100 text-teal-700",
  REJECTED: "bg-red-100 text-red-700",
};

export default function AppliedPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const FILTERS = ["ALL", "SUBMITTED", "INTERVIEW", "OFFER", "REJECTED"];

  useEffect(() => {
    setLoading(true);
    // Fetch all post-apply statuses
    const fetches = ["SUBMITTED", "INTERVIEW", "OFFER", "REJECTED"].map((s) =>
      api<Job[]>(`/api/jobs?status=${s}&limit=500`).catch(() => [])
    );
    Promise.all(fetches).then((results) => {
      const all = results.flat().sort((a, b) => {
        const da = a.date_applied ? new Date(a.date_applied).getTime() : 0;
        const db = b.date_applied ? new Date(b.date_applied).getTime() : 0;
        return db - da;
      });
      setJobs(all);
      setLoading(false);
    });
  }, []);

  const filtered =
    filter === "ALL" ? jobs : jobs.filter((j) => j.status === filter);

  function copyEmail(jobId: number, email: string) {
    navigator.clipboard.writeText(email);
    setCopiedId(jobId);
    setTimeout(() => setCopiedId(null), 2000);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Applied Jobs</h1>
      <p className="text-sm text-gray-500 mb-4">
        All applications with the email address used for each.
      </p>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2 mb-4">
        {FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded text-xs font-medium border ${
              filter === s
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {s === "ALL" ? `All (${jobs.length})` : `${s} (${jobs.filter((j) => j.status === s).length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : filtered.length === 0 ? (
        <p className="text-gray-500">No applied jobs found.</p>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Position</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Email Used</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Applied</th>
                <th className="px-4 py-3">Link</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {job.company}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{job.title}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {job.location || "—"}
                  </td>
                  <td className="px-4 py-3">
                    {job.email_used ? (
                      <button
                        onClick={() => copyEmail(job.id, job.email_used!)}
                        className="text-xs font-mono text-gray-700 hover:text-blue-600 cursor-pointer"
                        title="Click to copy"
                      >
                        {job.email_used}
                        {copiedId === job.id && (
                          <span className="ml-1 text-green-600">✓</span>
                        )}
                      </button>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        STATUS_COLORS[job.status] || "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {job.date_applied
                      ? new Date(job.date_applied).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {job.source_url ? (
                      <a
                        href={job.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
