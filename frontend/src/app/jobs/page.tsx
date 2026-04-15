"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  score: number;
  status: string;
  date_found: string | null;
  source: string | null;
}

const STATUSES = [
  "ALL", "FOUND", "MATCHED", "REVIEW_NEEDED", "DRAFTED", "APPLYING",
  "SUBMITTED", "FAILED", "SKIPPED", "DUPLICATE", "REJECTED", "INTERVIEW", "OFFER", "WITHDRAWN",
];

const STATUS_COLORS: Record<string, string> = {
  FOUND: "bg-gray-100 text-gray-700",
  MATCHED: "bg-green-100 text-green-700",
  REVIEW_NEEDED: "bg-yellow-100 text-yellow-700",
  DRAFTED: "bg-blue-100 text-blue-700",
  APPLYING: "bg-indigo-100 text-indigo-700",
  SUBMITTED: "bg-purple-100 text-purple-700",
  FAILED: "bg-red-100 text-red-700",
  SKIPPED: "bg-gray-100 text-gray-500",
  DUPLICATE: "bg-gray-100 text-gray-400",
  REJECTED: "bg-red-50 text-red-600",
  INTERVIEW: "bg-emerald-100 text-emerald-700",
  OFFER: "bg-teal-100 text-teal-700",
  WITHDRAWN: "bg-gray-200 text-gray-500",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");

  useEffect(() => {
    setLoading(true);
    const params = filter === "ALL" ? "" : `?status=${filter}`;
    api<Job[]>(`/api/jobs${params}`)
      .then(setJobs)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Jobs</h1>

      <div className="flex flex-wrap gap-2 mb-4">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded text-xs font-medium border ${
              filter === s
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : jobs.length === 0 ? (
        <p className="text-gray-500">No jobs found.</p>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Found</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {jobs.map((job) => (
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
                  <td className="px-4 py-3 text-gray-500">
                    {job.location || "—"}
                  </td>
                  <td className="px-4 py-3 font-mono">{job.score}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        STATUS_COLORS[job.status] || "bg-gray-100"
                      }`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {job.date_found
                      ? new Date(job.date_found).toLocaleDateString()
                      : "—"}
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
