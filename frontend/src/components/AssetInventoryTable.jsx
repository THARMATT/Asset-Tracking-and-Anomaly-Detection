// ==========================================
// ASSET INVENTORY TABLE COMPONENT
// ==========================================

import React, { useState } from 'react';
import { ShieldCheck, ShieldX, Search, Layers, Loader2 } from 'lucide-react';

export default function AssetInventoryTable({
  assets,
  isLoading,
  onToggleAuthorization,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [togglingId, setTogglingId] = useState(null);

  const filteredAssets = (assets || []).filter((a) => {
    const q = searchTerm.toLowerCase();
    return (
      a.asset_id?.toLowerCase().includes(q) ||
      a.asset_name?.toLowerCase().includes(q) ||
      a.expected_zone?.toLowerCase().includes(q) ||
      a.category?.toLowerCase().includes(q)
    );
  });

  const handleToggle = async (asset) => {
    try {
      setTogglingId(asset.asset_id);
      await onToggleAuthorization(
        asset.asset_id,
        !asset.authorized_exit,
        asset.authorized_exit ? 'Revoked via dashboard' : 'Granted via dashboard'
      );
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <section className="table-card" aria-label="Registered Physical Assets">
      <div className="table-header-row">
        <div>
          <h2 className="table-title">Registered Physical Assets</h2>
          <p className="table-subtitle">
            Monitored inventory, assigned storage zones, and gate exit permits
          </p>
        </div>

        <div className="table-actions">
          <div className="search-box">
            <Search className="search-icon" aria-hidden="true" />
            <input
              type="text"
              placeholder="Search assets by ID, name, or shelf..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
              aria-label="Filter asset inventory"
            />
          </div>
        </div>
      </div>

      {isLoading && (!assets || assets.length === 0) ? (
        <div className="table-loading">
          <Loader2 className="spin icon-md" aria-hidden="true" />
          <span>Loading asset records...</span>
        </div>
      ) : filteredAssets.length === 0 ? (
        <div className="table-empty">
          <Layers className="empty-icon text-muted" aria-hidden="true" />
          <p className="empty-text">No registered assets found.</p>
          <span className="empty-subtext">
            {searchTerm
              ? `No items matching search query "${searchTerm}".`
              : 'The database contains zero assets. Run seed script or add items via API.'}
          </span>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Asset ID</th>
                <th scope="col">Name</th>
                <th scope="col">Category</th>
                <th scope="col">Expected Zone</th>
                <th scope="col">Exit Authorization</th>
                <th scope="col">Status</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssets.map((asset) => {
                const isAuth = Boolean(asset.authorized_exit);
                const isToggling = togglingId === asset.asset_id;

                return (
                  <tr key={asset.asset_id}>
                    <td>
                      <span className="mono-badge font-bold">{asset.asset_id}</span>
                    </td>
                    <td>
                      <span className="asset-name-cell">{asset.asset_name}</span>
                    </td>
                    <td>
                      <span className="text-secondary">{asset.category || 'General'}</span>
                    </td>
                    <td>
                      <span className="zone-pill">{asset.expected_zone}</span>
                    </td>
                    <td>
                      {isAuth ? (
                        <span className="badge badge-success inline-flex-center">
                          <ShieldCheck className="icon-xs mr-1" aria-hidden="true" />
                          Authorized
                        </span>
                      ) : (
                        <span className="badge badge-danger inline-flex-center">
                          <ShieldX className="icon-xs mr-1" aria-hidden="true" />
                          Unauthorized
                        </span>
                      )}
                    </td>
                    <td>
                      {asset.active ? (
                        <span className="status-dot-active" title="Active">
                          Active
                        </span>
                      ) : (
                        <span className="status-dot-inactive" title="Inactive">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        onClick={() => handleToggle(asset)}
                        disabled={isToggling}
                        className={`btn btn-sm ${
                          isAuth ? 'btn-outline-danger' : 'btn-outline-success'
                        }`}
                        title={
                          isAuth
                            ? 'Revoke gate exit authorization'
                            : 'Grant gate exit authorization'
                        }
                        aria-label={`${
                          isAuth ? 'Revoke exit authorization for' : 'Grant exit authorization for'
                        } ${asset.asset_id}`}
                      >
                        {isToggling ? (
                          <Loader2 className="spin icon-xs" aria-hidden="true" />
                        ) : isAuth ? (
                          'Revoke Exit'
                        ) : (
                          'Authorize Exit'
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
