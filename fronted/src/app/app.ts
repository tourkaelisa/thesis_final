import { CommonModule } from '@angular/common';
import { AfterViewInit, Component, ElementRef, HostListener, ViewChild, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatToolbarModule } from '@angular/material/toolbar';
import { AuthService } from './services/auth';
import { MatIconModule } from '@angular/material/icon';
import { filter } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule, MatButtonModule, MatIconModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class App implements AfterViewInit {
  private auth = inject(AuthService);
  private router = inject(Router);

  @ViewChild('topNav') topNav?: ElementRef<HTMLElement>;

  // Θέση/πλάτος του φωτεινού indicator κάτω από τον ενεργό σύνδεσμο.
  indicatorLeft = signal(0);
  indicatorWidth = signal(0);

  currentUser = this.auth.currentUser;
  userInitials = computed(() => {
    const user = this.currentUser();
    return user ? `${user.firstName.charAt(0)}${user.lastName.charAt(0)}`.toUpperCase() : '';
  });

  sidebarOpen = false;

  categories = [
    { label: 'Laptops', route: '/laptops' },
    { label: 'Κινητά', route: '/mobiles' },
    { label: 'Tablets', route: '/tablets' },
    { label: 'Τηλεοράσεις', route: '/tvs' },
    { label: 'Smartwatches', route: '/smartwatches' },
    { label: 'Σταθεροί Υπολογιστές', route: '/desktops' },
    { label: 'Οθόνες', route: '/monitors' },
    { label: 'Ακουστικά', route: '/headphones' },
    { label: 'Κονσόλες', route: '/consoles' }
  ];

  constructor() {
    // Κάθε αλλαγή σελίδας μετακινεί το φωτεινό underline στον ενεργό σύνδεσμο.
    this.router.events
      .pipe(filter(e => e instanceof NavigationEnd))
      .subscribe(() => this.scheduleIndicatorUpdate());
  }

  ngAfterViewInit(): void {
    this.scheduleIndicatorUpdate();
  }

  @HostListener('window:resize')
  onResize(): void {
    this.updateIndicator();
  }

  private scheduleIndicatorUpdate(): void {
    // Μικρή καθυστέρηση ώστε να προλάβει το routerLinkActive να εφαρμοστεί στο DOM.
    setTimeout(() => this.updateIndicator(), 0);
  }

  private updateIndicator(): void {
    const nav = this.topNav?.nativeElement;
    const active = nav?.querySelector<HTMLElement>('a.active');
    if (active) {
      this.indicatorLeft.set(active.offsetLeft);
      this.indicatorWidth.set(active.offsetWidth);
    } else {
      // Σελίδα κατηγορίας ή άλλη — κανένα link ενεργό, κρύβουμε το underline.
      this.indicatorWidth.set(0);
    }
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  closeSidebar(): void {
    this.sidebarOpen = false;
  }

  logout(): void {
    this.auth.clearUser();
    this.router.navigateByUrl('/');
  }
}
