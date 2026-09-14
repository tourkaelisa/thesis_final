import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable } from 'rxjs';
import { AuthService } from './auth';

@Injectable({
  providedIn: 'root'
})
export class DataStreamService {
  private socket$: WebSocketSubject<any>;
  private auth = inject(AuthService);
  private router = inject(Router);

  constructor() {
    // Σύνδεση στον FastAPI WebSocket Server (της Python) μέσω same-origin.
    // Έτσι ο proxy (dev-server proxy.conf.json / nginx στο prod) προωθεί το
    // /ws/shop στο backend service — ο browser δεν χρειάζεται να ξέρει το host.
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    this.socket$ = webSocket(`${wsProtocol}://${window.location.host}/ws/shop`);

    // Eager connect: ανοίγουμε το WebSocket αμέσως στο bootstrap ώστε το
    // handshake να τρέχει παράλληλα με τη φόρτωση της Angular. Έτσι όταν η
    // πρώτη σελίδα ζητάει δεδομένα, η σύνδεση είναι συνήθως ήδη ανοιχτή.
    // Αυτό το subscribe κρατάει μία κοινή σύνδεση ζωντανή για όλη την εφαρμογή
    // και χειρίζεται κεντρικά την περίπτωση άκυρου token (AUTH_INVALID).
    this.socket$.subscribe({
      next: (message) => this.handleAuthInvalid(message),
      error: () => {}
    });
  }

  // Αν ο server απαντήσει ότι το token είναι άκυρο/ληγμένο, κάνουμε καθαρό
  // logout και γυρνάμε στην αρχική (αυτήν που βλέπουν οι μη συνδεδεμένοι
  // χρήστες) — αντί να μένουν άδειες οι λίστες.
  private handleAuthInvalid(message: any): void {
    if (message?.type !== 'AUTH_INVALID') return;
    if (!this.auth.currentUser()) return; 
    this.auth.clearUser();
    this.router.navigate(['/']);
  }

  // Στέλνουμε αίτημα στην Python, επισυνάπτοντας πάντα το JWT (αν υπάρχει).
  // Έτσι ο server επικυρώνει μόνος του τα δικαιώματα από το υπογεγραμμένο
  // token — η ταυτότητα/ρόλος δεν στέλνεται ποτέ ως απλό πεδίο από τον client.
  private send(message: any): void {
    const token = this.auth.getToken();
    this.socket$.next(token ? { ...message, token } : message);
  }

  listenToStore(): Observable<any> {
    return this.socket$.asObservable();
  }

  requestRecommendations(productId: string) {
    this.send({ action: 'get_recommendations', productId });
  }

  getProductDetails(productId: string) {
    this.send({ action: 'get_product_details', productId });
  }

  requestCategory(categoryName: string) {
    this.send({ action: 'get_category', category: categoryName });
  }

  addToWishlist(productId: string) {
    this.send({ action: 'add_to_wishlist', productId });
  }

  getWishlist() {
    this.send({ action: 'get_wishlist' });
  }

  removeFromWishlist(productId: string) {
    this.send({ action: 'remove_from_wishlist', productId });
  }

  requestPopularProducts() {
    this.send({ action: 'get_popular_products' });
  }

  keywordSearch(query: string) {
    this.send({ action: 'keyword_search', query });
  }

  requestPersonalizedRecommendations() {
    this.send({ action: 'get_personalized_recommendations' });
  }

  requestDashboardStats() {
    this.send({ action: 'get_dashboard_stats' });
  }

  searchCategory(
    category: string,
    filters: { [key: string]: string[] },
    propRanges: { [key: string]: { min: number; max: number } },
    priceMin: number,
    priceMax: number
  ) {
    this.send({
      action: 'search_category',
      category,
      filters,
      propRanges,
      priceMin,
      priceMax
    });
  }
}
