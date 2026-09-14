import { Component, ElementRef, OnDestroy, OnInit, computed, effect, inject, signal, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Subscription } from 'rxjs';
import Chart from 'chart.js/auto';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';

interface RegPoint { date: string; count: number; cumulative: number; }

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonToggleModule, MatProgressBarModule],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css']
})
export class Dashboard implements OnInit, OnDestroy {
  private auth = inject(AuthService);
  private streamService = inject(DataStreamService);
  private router = inject(Router);

  stats = signal<any>(null);
  lastUpdated = signal<Date | null>(null);
  private statsSub?: Subscription;

  chartMode = signal<'cumulative' | 'daily'>('cumulative');
  wlMode = signal<'day' | 'week'>('day');

  private regCanvas = viewChild<ElementRef<HTMLCanvasElement>>('regCanvas');
  private wlCanvas = viewChild<ElementRef<HTMLCanvasElement>>('wlCanvas');
  private engCanvas = viewChild<ElementRef<HTMLCanvasElement>>('engCanvas');

  private regChart?: Chart;
  private wlChartObj?: Chart;
  private engChart?: Chart;

  constructor() {
    effect(() => this.renderRegistrations());
    effect(() => this.renderWishlist());
    effect(() => this.renderEngagement());
  }

  ngOnInit() {
    const user = this.auth.currentUser();
    if (!user) {
      this.router.navigateByUrl('/login');
      return;
    }
    if (user.role !== 2) {
      this.router.navigateByUrl('/');
      return;
    }

    this.statsSub = this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'DASHBOARD_STATS') {
        this.stats.set(msg);
        this.lastUpdated.set(new Date());
      }
    });

    this.load();
  }

  ngOnDestroy() {
    this.statsSub?.unsubscribe();
    this.regChart?.destroy();
    this.wlChartObj?.destroy();
    this.engChart?.destroy();
  }

  load() {
    this.streamService.requestDashboardStats();
  }

  setMode(mode: 'cumulative' | 'daily') {
    if (mode) this.chartMode.set(mode);
  }

  setWlMode(mode: 'day' | 'week') {
    if (mode) this.wlMode.set(mode);
  }

  //  Γραφήματα (Chart.js)

  private axisOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: 'rgba(6,182,212,0.14)' }, ticks: { color: '#94a3b8' } },
        x: { grid: { display: false }, ticks: { color: '#94a3b8', maxRotation: 0, autoSkip: true } },
      },
    } as any;
  }

  /** Γραμμικό: εγγραφές χρηστών (σωρευτικά ή ανά ημέρα). */
  private renderRegistrations() {
    const el = this.regCanvas()?.nativeElement;
    const t = this.stats()?.registrations_timeline as RegPoint[] | undefined;
    if (!el || !t?.length) return;

    const mode = this.chartMode();
    const labels = t.map(d => this.shortDate(d.date));
    const data = t.map(d => (mode === 'cumulative' ? d.cumulative : d.count));

    if (!this.regChart) {
      const ctx = el.getContext('2d')!;
      const fill = ctx.createLinearGradient(0, 0, 0, 300);
      fill.addColorStop(0, 'rgba(6,182,212,0.38)');
      fill.addColorStop(1, 'rgba(6,182,212,0)');
      this.regChart = new Chart(el, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            data,
            borderColor: '#0284c7',
            backgroundColor: fill,
            fill: true,
            cubicInterpolationMode: 'monotone', // χωρίς overshoot — δεν πέφτει κάτω από το 0
            tension: 0,
            borderWidth: 3,
            pointRadius: 3,
            pointBackgroundColor: '#fff',
            pointBorderColor: '#0891b2',
            pointBorderWidth: 2,
          }],
        },
        options: this.axisOptions(),
      });
    } else {
      this.regChart.data.labels = labels;
      this.regChart.data.datasets[0].data = data;
      this.regChart.update();
    }
  }

  /** Ραβδόγραμμα: προσθήκες στη λίστα επιθυμιών (ανά ημέρα ή εβδομάδα). */
  private renderWishlist() {
    const el = this.wlCanvas()?.nativeElement;
    const raw = this.stats()?.wishlist_activity as { date: string; count: number }[] | undefined;
    if (!el || !raw?.length) return;

    const buckets = this.wlMode() === 'week'
      ? this.toWeekly(raw)
      : raw.map(d => ({ label: this.shortDate(d.date), count: d.count }));
    const labels = buckets.map(b => b.label);
    const data = buckets.map(b => b.count);

    if (!this.wlChartObj) {
      const ctx = el.getContext('2d')!;
      const fill = ctx.createLinearGradient(0, 0, 0, 260);
      fill.addColorStop(0, '#06b6d4');
      fill.addColorStop(1, '#0e7490');
      this.wlChartObj = new Chart(el, {
        type: 'bar',
        data: { labels, datasets: [{ data, backgroundColor: fill, borderRadius: 5, maxBarThickness: 44 }] },
        options: this.axisOptions(),
      });
    } else {
      this.wlChartObj.data.labels = labels;
      this.wlChartObj.data.datasets[0].data = data;
      this.wlChartObj.update();
    }
  }

  /** Donut: αναλογία ενεργών / ανενεργών χρηστών. */
  private renderEngagement() {
    const el = this.engCanvas()?.nativeElement;
    const e = this.engagement();
    if (!el || !e || !e.total_users) return;

    const data = [e.active_users, e.inactive_users];

    if (!this.engChart) {
      const ctx = el.getContext('2d')!;
      const arc = ctx.createLinearGradient(0, 0, 150, 0);
      arc.addColorStop(0, '#0284c7');
      arc.addColorStop(1, '#06b6d4');
      this.engChart = new Chart(el, {
        type: 'doughnut',
        data: {
          labels: ['Ενεργοί', 'Ανενεργοί'],
          datasets: [{ data, backgroundColor: [arc, '#e5e7eb'], borderWidth: 0, borderRadius: 12, spacing: 2 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          plugins: { legend: { display: false } }, 
        } as any,
      });
    } else {
      this.engChart.data.datasets[0].data = data;
      this.engChart.update();
    }
  }

  /** Άθροιση των ημερήσιων τιμών σε εβδομαδιαίους κάδους (7άδες). */
  private toWeekly(raw: { date: string; count: number }[]) {
    const out: { label: string; count: number }[] = [];
    for (let i = 0; i < raw.length; i += 7) {
      const chunk = raw.slice(i, i + 7);
      out.push({ label: this.shortDate(chunk[0].date), count: chunk.reduce((s, d) => s + d.count, 0) });
    }
    return out;
  }

  maxPopularity(): number {
    const stats = this.stats();
    if (!stats?.top_products?.length) return 1;
    return stats.top_products[0].popularity;
  }

  /** Σύνοψη εγγραφών: σύνολο περιόδου, κορύφωση, τρέχον σύνολο. */
  regSummary = computed(() => {
    const t = this.stats()?.registrations_timeline as RegPoint[] | undefined;
    if (!t?.length) return null;
    const periodTotal = t.reduce((s, d) => s + d.count, 0);
    const peak = t.reduce((m, d) => (d.count > m.count ? d : m), t[0]);
    return {
      periodTotal,
      currentTotal: t[t.length - 1].cumulative,
      peakCount: peak.count,
      peakDate: peak.date,
      days: t.length,
    };
  });

  /** Σύνοψη wishlist: σύνολο προσθηκών, κορύφωση, μέσος όρος/ημέρα. */
  wlSummary = computed(() => {
    const raw = this.stats()?.wishlist_activity as { date: string; count: number }[] | undefined;
    if (!raw?.length) return null;
    const total = raw.reduce((s, d) => s + d.count, 0);
    const peak = raw.reduce((m, d) => (d.count > m.count ? d : m), raw[0]);
    return { total, peakCount: peak.count, peakDate: peak.date, avg: total / raw.length, days: raw.length };
  });

  engagement = computed(() => this.stats()?.engagement ?? null);

  /** Κατανομή μεγέθους λίστας, κανονικοποιημένη ως προς τον μεγαλύτερο κάδο. */
  distRows = computed(() => {
    const dist = this.engagement()?.distribution as { label: string; count: number }[] | undefined;
    if (!dist?.length) return [];
    const max = Math.max(1, ...dist.map(d => d.count));
    return dist.map(d => ({ ...d, pct: (d.count / max) * 100 }));
  });

  abandoned = computed(() => (this.stats()?.abandoned_products ?? []) as any[]);

  /** Μέγιστες συνολικές προσθήκες — για κανονικοποίηση του μήκους των μπαρών. */
  maxAbandonAdditions = computed(() => {
    const a = this.abandoned();
    return a.length ? Math.max(...a.map(p => p.additions)) : 1;
  });

  //helpers ημερομηνιών

  /** "2026-06-12" → "12/6" */
  shortDate(iso: string): string {
    const [, m, d] = iso.split('-');
    return `${parseInt(d, 10)}/${parseInt(m, 10)}`;
  }

  /** "2026-06-12" → "12 Ιουν" */
  prettyDate(iso: string): string {
    const months = ['Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μαϊ', 'Ιουν', 'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ'];
    const [, m, d] = iso.split('-');
    return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]}`;
  }
}
