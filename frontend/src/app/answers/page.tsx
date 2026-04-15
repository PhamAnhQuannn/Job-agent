"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";

interface Answer {
  id: number;
  question_pattern: string;
  answer: string;
  category: string | null;
}

export default function AnswersPage() {
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ question_pattern: "", answer: "", category: "" });
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = () => {
    api<Answer[]>("/api/answers")
      .then(setAnswers)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId) {
      await api(`/api/answers/${editingId}`, {
        method: "PUT",
        body: JSON.stringify(form),
      });
    } else {
      await api("/api/answers", {
        method: "POST",
        body: JSON.stringify(form),
      });
    }
    setForm({ question_pattern: "", answer: "", category: "" });
    setEditingId(null);
    load();
  };

  const handleDelete = async (id: number) => {
    await api(`/api/answers/${id}`, { method: "DELETE" });
    load();
  };

  const startEdit = (a: Answer) => {
    setEditingId(a.id);
    setForm({
      question_pattern: a.question_pattern,
      answer: a.answer,
      category: a.category || "",
    });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Answer Bank</h1>

      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-4 mb-6 space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            Question Pattern
          </label>
          <input
            className="w-full border rounded px-3 py-1.5 text-sm"
            placeholder='e.g. "Why do you want to work here?"'
            value={form.question_pattern}
            onChange={(e) => setForm({ ...form, question_pattern: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            Answer
          </label>
          <textarea
            className="w-full border rounded px-3 py-1.5 text-sm"
            rows={3}
            value={form.answer}
            onChange={(e) => setForm({ ...form, answer: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            Category
          </label>
          <input
            className="w-full border rounded px-3 py-1.5 text-sm"
            placeholder="e.g. motivation, experience, technical"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          />
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
          >
            {editingId ? "Update" : "Add"}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={() => {
                setEditingId(null);
                setForm({ question_pattern: "", answer: "", category: "" });
              }}
              className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400 text-sm"
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : answers.length === 0 ? (
        <p className="text-gray-500">No answers yet. Add one above.</p>
      ) : (
        <div className="space-y-3">
          {answers.map((a) => (
            <div key={a.id} className="bg-white shadow rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  {a.category && (
                    <span className="inline-block text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded mb-1">
                      {a.category}
                    </span>
                  )}
                  <p className="font-medium text-sm">{a.question_pattern}</p>
                  <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">
                    {a.answer}
                  </p>
                </div>
                <div className="flex gap-2 ml-4">
                  <button
                    onClick={() => startEdit(a)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
