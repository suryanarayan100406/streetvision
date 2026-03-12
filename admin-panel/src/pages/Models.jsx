import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Models() {
  const { data: models, refetch } = useFetch('/admin/models/');

  const activate = async (id) => {
    await api.post(`/admin/models/${id}/activate`);
    toast.success('Model activated');
    refetch();
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">ML Models</h2>

      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Model</th>
              <th className="text-left px-4 py-3">Version</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Precision</th>
              <th className="text-left px-4 py-3">Recall</th>
              <th className="text-left px-4 py-3">F1</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {models?.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{m.model_name}</td>
                <td className="px-4 py-3">{m.version}</td>
                <td className="px-4 py-3">{m.model_type}</td>
                <td className="px-4 py-3">{m.precision?.toFixed(3) || '—'}</td>
                <td className="px-4 py-3">{m.recall?.toFixed(3) || '—'}</td>
                <td className="px-4 py-3">{m.f1_score?.toFixed(3) || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${m.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {m.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {!m.is_active && (
                    <button onClick={() => activate(m.id)} className="text-xs bg-primary-100 hover:bg-primary-200 text-primary-700 px-2 py-1 rounded">
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
