import { Injectable } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DataStreamService {
  private socket$: WebSocketSubject<any>;

  constructor() {
    // Σύνδεση στον FastAPI WebSocket Server (της Python)
    this.socket$ = webSocket('ws://localhost:8000/ws/shop');

    // Eager connect: ανοίγουμε το WebSocket αμέσως στο bootstrap ώστε το
    // handshake να τρέχει παράλληλα με τη φόρτωση της Angular. Έτσι όταν η
    // πρώτη σελίδα ζητάει δεδομένα, η σύνδεση είναι συνήθως ήδη ανοιχτή.
    // Το άδειο subscribe κρατάει μία κοινή σύνδεση ζωντανή για όλη την εφαρμογή.
    this.socket$.subscribe({ error: () => {} });
  }

  // Ακούμε για νέα δεδομένα από την Python
  listenToStore(): Observable<any> {
    return this.socket$.asObservable();
  }

  // Στέλνουμε αίτημα στην Python
  requestRecommendations(productId: string) {
    this.socket$.next({
      action: 'get_recommendations',
      productId: productId
    });
  }

  requestCategory(categoryName: string) {
    this.socket$.next({ action: 'get_category', category: categoryName });
  }

  addToWishlist(productId: string, userId?: number) {
    this.socket$.next({ action: 'add_to_wishlist', productId, userId });
  }

  getWishlist(userId: number) {
    this.socket$.next({ action: 'get_wishlist', userId });
  }

  removeFromWishlist(productId: string, userId: number) {
    this.socket$.next({ action: 'remove_from_wishlist', productId, userId });
  }

  requestPopularProducts() {
    this.socket$.next({ action: 'get_popular_products' });
  }

  semanticSearch(query: string) {
    this.socket$.next({ action: 'semantic_search', query });
  }

  requestPersonalizedRecommendations(userId: number) {
    this.socket$.next({ action: 'get_personalized_recommendations', userId });
  }

  requestDashboardStats() {
    this.socket$.next({ action: 'get_dashboard_stats' });
  }

  searchCategory(
    category: string,
    filters: { [key: string]: string[] },
    propRanges: { [key: string]: { min: number; max: number } },
    priceMin: number,
    priceMax: number
  ) {
    this.socket$.next({
      action: 'search_category',
      category,
      filters,
      propRanges,
      priceMin,
      priceMax
    });
  }
}