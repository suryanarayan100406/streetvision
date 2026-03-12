import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Scheduler() {
  const { data: tasks, refetch } = useFetch('/admin/scheduler/tasks');
  const { data: workers } = useFetch('/admin/scheduler/workers');

  const toggleTask = async (name, enabled) => {
    await api.patch(`/admin/scheduler/tasks/${name}`, { enabled: !enabled });
    toast.success(`Task ${!enabled ? 'enabled' : 'paused'}`);
    refetch();
  };

  const runNow = async (name) => {
    const { data } = await api.post(`/admin/scheduler/tasks/${name}/run-now`);
    toast.success(`Triggered: ${data.task_id}`);
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Task Scheduler</h2>

      {/* Workers */}
      <h3 className="text-lg font-semibold mb-3">Active Workers</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {workers?.map((w) => (
          <div key={w.name} className="bg-white rounded-lg border p-3">
            <p className="font-medium text-sm truncate">{w.name}</p>
            <p className="text-xs text-gray-500">{w.active_tasks} active tasks</p>
          </div>
        ))}
        {(!workers || workers.length === 0) && (
          <p className="text-gray-400 text-sm col-span-4">No workers connected</p>
        )}
      </div>

      {/* Tasks */}
      <h3 className="text-lg font-semibold mb-3">Scheduled Tasks</h3>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Task</th>
              <th className="text-left px-4 py-3">Schedule</th>
              <th className="text-left px-4 py-3">Queue</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tasks?.map((t) => (
              <tr key={t.name} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-xs">{t.name}</td>
                <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-[200px]">{t.task}</td>
                <td className="px-4 py-3 text-xs">{t.schedule_repr}</td>
                <td className="px-4 py-3 text-xs">{t.queue || 'default'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${t.enabled !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {t.enabled !== false ? 'Active' : 'Paused'}
                  </span>
                </td>
                <td className="px-4 py-3 flex gap-2">
                  <button onClick={() => toggleTask(t.name, t.enabled !== false)} className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded">
                    {t.enabled !== false ? 'Pause' : 'Resume'}
                  </button>
                  <button onClick={() => runNow(t.name)} className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded">
                    Run Now
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
