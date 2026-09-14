import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DataStreamService } from '../../services/data-stream';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

// Ετικέτες εμφάνισης ανά route κατηγορίας 
const CATEGORY_LABELS: { [key: string]: string } = {
  laptops: 'Laptops',
  mobiles: 'Κινητά',
  tablets: 'Tablets',
  tvs: 'Τηλεοράσεις',
  smartwatches: 'Smartwatches',
  desktops: 'Σταθεροί Υπολογιστές',
  monitors: 'Οθόνες',
  headphones: 'Ακουστικά',
  consoles: 'Κονσόλες',
};

interface QuantGroup {
  key: string; label: string;
  absMin: number; absMax: number;
  activeMin: number; activeMax: number;
}

@Component({
  selector: 'app-category',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatButtonModule, MatIconModule, RouterLink],
  templateUrl: './category.html',
  styleUrls: ['./category.css']
})
export class Category implements OnInit {
  products = signal<any[]>([]);
  filteredProducts = signal<any[]>([]);
  categoryName = signal('');
  categoryLabel = computed(() => CATEGORY_LABELS[this.categoryName()] ?? this.categoryName());

  filtersOpen = false;
  searching = signal(false);

  filterGroups = signal<{ key: string; label: string; values: string[] }[]>([]);
  filterSelections: { [key: string]: string[] } = {};

  quantGroups = signal<QuantGroup[]>([]);

  priceMin = 0;
  priceMax = 0;
  filterPriceMin = 0;
  filterPriceMax = 0;

  private readonly FIELD_LABELS: { [k: string]: string } = {
    brand:            'Μάρκα',
    os:               'Λειτουργικό Σύστημα',
    color:            'Χρώμα',
    definition:       'Ανάλυση Εικόνας',
    cpu:              'Επεξεργαστής (CPU)',
    releaseDate:      'Έτος Κυκλοφορίας',
    resolution:       'Ανάλυση Οθόνης',
    ram:              'Μνήμη RAM (GB)',
    storage:          'Αποθήκευση (GB)',
    screen_size:      "Μέγεθος Οθόνης (\")",
    battery:          'Μπαταρία (mAh)',
    camera_main_mp:   'Κάμερα (MP)',
    camera_selfie_mp: 'Selfie Κάμερα (MP)',
    refresh_rate:     'Ρυθμός Ανανέωσης (Hz)',
    weight:           'Βάρος (kg)',
    ram_type:         'Τύπος RAM',
    storage_type:     'Τύπος Δίσκου',
    console_platform: 'Πλατφόρμα',
    console_edition:  'Έκδοση',
    console_bundle:   'Πακέτο',
    use_case:         'Χρήση',
    headphone_type:   'Είδος',
    connection_type:  'Συνδεσιμότητα',
    gpu_memory:       'Μνήμη Κάρτας',
    case_size:        'Μέγεθος Κουτιού',
    is_portable:      'Φορητή',
    has_anc:          'Active Noise Cancellation',
    cpu_frequency:    'Συχνότητα Επεξεργαστή (GHz)',
    hdr_support:      'Υποστήριξη HDR',
    height_adjustment: 'Ρύθμιση Ύψους',
    is_curved:        'Curved',
    is_ultrawide:     'Ultrawide',
    panel_type:       'Τύπος Panel',
    response_time:    'Χρόνος Απόκρισης (ms)',
    vesa_mount:       'Βάση VESA (mm)',
    battery_hours:    'Μπαταρία (ώρες)',
  };

  private readonly EXCLUDED_PROPS = new Set(['resolution_width', 'resolution_height', 'vesa_width', 'vesa_height']);

  private readonly WEIGHT_GRAMS_CATEGORIES = new Set(['mobiles', 'tablets', 'smartwatches']);

  constructor(
    private route: ActivatedRoute,
    private streamService: DataStreamService
  ) {
    this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'CATEGORY_UPDATED') {
        this.products.set(msg.products);
        this.filteredProducts.set([...msg.products]);
        this.buildFilters();
      } else if (msg.type === 'SEARCH_RESULTS') {
        this.searching.set(false);
        this.filteredProducts.set(msg.products);
      }
    });
  }

  ngOnInit() {
    this.route.params.subscribe(params => {
      this.categoryName.set(params['name']);
      this.products.set([]);
      this.filteredProducts.set([]);
      this.filterGroups.set([]);
      this.filterSelections = {};
      this.quantGroups.set([]);
      this.filtersOpen = false;
      this.streamService.requestCategory(params['name']);
    });
  }

  private quantLabel(key: string): string {
    if (key === 'weight') {
      return this.WEIGHT_GRAMS_CATEGORIES.has(this.categoryName())
        ? 'Βάρος (gr)'
        : 'Βάρος (kg)';
    }
    return this.FIELD_LABELS[key] ?? key.replace(/_/g, ' ');
  }

  private buildFilters() {
    const products = this.products();

    const NON_FILTER = new Set(['id', 'name', 'image', 'price', 'popularity', 'props']);
    const stringFields = new Set<string>();
    products.forEach(p => {
      Object.keys(p).forEach(k => {
        if (!NON_FILTER.has(k) && typeof p[k] === 'string') stringFields.add(k);
      });
    });

    const groups: { key: string; label: string; values: string[] }[] = [];
    for (const field of Array.from(stringFields).sort()) {
      const vals = new Set<string>();
      products.forEach(p => { if (p[field]) vals.add(p[field]); });
      if (vals.size > 1) {
        groups.push({ key: field, label: this.FIELD_LABELS[field] ?? field.replace(/_/g, ' '), values: Array.from(vals).sort() });
      }
    }
    this.filterGroups.set(groups);

    const propKeys = new Set<string>();
    products.forEach(p => p.props && Object.keys(p.props).forEach(k => propKeys.add(k)));

    const quantGroups: QuantGroup[] = [];
    for (const key of Array.from(propKeys).sort()) {
      if (this.EXCLUDED_PROPS.has(key)) continue;
      const nums = products
        .map(p => p.props?.[key])
        .filter(v => v !== undefined)
        .map(Number)
        .filter(v => !isNaN(v));
      if (nums.length === 0) continue;
      const absMin = Math.min(...nums);
      const absMax = Math.max(...nums);
      if (absMin === absMax) continue;
      quantGroups.push({
        key, absMin, absMax, activeMin: absMin, activeMax: absMax,
        label: this.quantLabel(key)
      });
    }
    this.quantGroups.set(quantGroups);

    const prices = products.map(p => p.price).filter(Boolean);
    this.priceMin = Math.floor(Math.min(...prices));
    this.priceMax = Math.ceil(Math.max(...prices));
    this.filterPriceMin = this.priceMin;
    this.filterPriceMax = this.priceMax;
  }

  toggleFilter(key: string, value: string) {
    if (!this.filterSelections[key]) this.filterSelections[key] = [];
    const idx = this.filterSelections[key].indexOf(value);
    if (idx >= 0) {
      this.filterSelections[key] = this.filterSelections[key].filter(v => v !== value);
    } else {
      this.filterSelections[key] = [...this.filterSelections[key], value];
    }
  }

  isChecked(key: string, value: string): boolean {
    return this.filterSelections[key]?.includes(value) ?? false;
  }

  get activeFilterCount(): number {
    const sel = Object.values(this.filterSelections).reduce((s, a) => s + (a?.length ?? 0), 0);
    const price = this.filterPriceMin > this.priceMin || this.filterPriceMax < this.priceMax ? 1 : 0;
    const quant = this.quantGroups().filter(g => g.activeMin > g.absMin || g.activeMax < g.absMax).length;
    return sel + price + quant;
  }

  search() {
    this.searching.set(true);
    const propRanges: { [key: string]: { min: number; max: number } } = {};
    for (const g of this.quantGroups()) {
      if (g.activeMin > g.absMin || g.activeMax < g.absMax) {
        propRanges[g.key] = { min: g.activeMin, max: g.activeMax };
      }
    }
    this.streamService.searchCategory(
      this.categoryName(),
      this.filterSelections,
      propRanges,
      this.filterPriceMin,
      this.filterPriceMax
    );
  }

  clearFilters() {
    this.filterSelections = {};
    this.filterPriceMin = this.priceMin;
    this.filterPriceMax = this.priceMax;
    this.quantGroups.update(groups => {
      groups.forEach(g => { g.activeMin = g.absMin; g.activeMax = g.absMax; });
      return [...groups];
    });
    this.filteredProducts.set([...this.products()]);
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }
}
