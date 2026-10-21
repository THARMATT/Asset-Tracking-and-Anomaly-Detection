// ==========================================
// SUMMARY CARDS COMPONENT
// ==========================================

import React from 'react';
import {
  Boxes,
  Activity,
  MapPinOff,
  ShieldAlert,
  HelpCircle,
  ClipboardCheck,
} from 'lucide-react';

export default function SummaryCards({ summary }) {
  const s = summary || {};
  const defs = s.definitions || {};

  const cards = [
    {
      id: 'registered_assets',
      title: 'Registered Assets',
      value: s.registered_assets ?? 0,
      subtext: `${s.active_assets ?? 0} currently active`,
      description: defs.registered_assets || 'Total physical assets cataloged in the system',
      icon: Boxes,
      cardClass: 'card-default',
      iconClass: 'icon-blue',
    },
    {
      id: 'total_events',
      title: 'Total Scans',
      value: s.total_events ?? 0,
      subtext: `${s.normal_events ?? 0} verified normal`,
      description: defs.total_events || 'Cumulative tracking scans recorded in database',
      icon: Activity,
      cardClass: 'card-default',
      iconClass: 'icon-cyan',
    },
    {
      id: 'misplaced_events',
      title: 'Misplaced Assets',
      value: s.misplaced_events ?? 0,
      subtext: 'Wrong shelf location',
      description: defs.misplaced_events || 'Assets detected outside expected storage zone',
      icon: MapPinOff,
      cardClass: s.misplaced_events > 0 ? 'card-warning' : 'card-default',
      iconClass: 'icon-yellow',
    },
    {
      id: 'unauthorized_exits',
      title: 'Unauthorized Exits',
      value: s.unauthorized_exits ?? 0,
      subtext: 'Gate security alerts',
      description: defs.unauthorized_exits || 'Perimeter breaches: detected at gate without permit',
      icon: ShieldAlert,
      cardClass: s.unauthorized_exits > 0 ? 'card-danger' : 'card-default',
      iconClass: 'icon-red',
    },
    {
      id: 'unknown_assets',
      title: 'Unknown Assets',
      value: s.unknown_assets ?? 0,
      subtext: 'Uncataloged RFIDs/Tags',
      description: defs.unknown_assets || 'Scans referencing unregistered asset IDs',
      icon: HelpCircle,
      cardClass: s.unknown_assets > 0 ? 'card-purple' : 'card-default',
      iconClass: 'icon-purple',
    },
    {
      id: 'missing_investigations',
      title: 'Missing Investigations',
      value: s.missing_investigations ?? 0,
      subtext: 'Flagged in audit',
      description: defs.missing_investigations || 'Assets absent during formal inventory audits',
      icon: ClipboardCheck,
      cardClass: s.missing_investigations > 0 ? 'card-orange' : 'card-default',
      iconClass: 'icon-orange',
    },
  ];

  return (
    <section className="summary-grid" aria-label="System Metrics Summary">
      {cards.map((card) => {
        const IconComponent = card.icon;
        return (
          <article
            key={card.id}
            className={`metric-card ${card.cardClass}`}
            title={card.description}
          >
            <div className="metric-header">
              <span className="metric-title">{card.title}</span>
              <div className={`metric-icon-box ${card.iconClass}`}>
                <IconComponent className="icon-md" aria-hidden="true" />
              </div>
            </div>
            <div className="metric-body">
              <span className="metric-value">{card.value}</span>
              <span className="metric-subtext">{card.subtext}</span>
            </div>
            <p className="metric-tooltip">{card.description}</p>
          </article>
        );
      })}
    </section>
  );
}
