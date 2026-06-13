import { Injectable, signal } from '@angular/core';

export interface CurrentUser {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: number;
  token: string;
}

const STORAGE_KEY = 'semantic-shop-user';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly currentUserSignal = signal<CurrentUser | null>(this.loadUser());

  readonly currentUser = this.currentUserSignal.asReadonly();

  setUser(user: CurrentUser): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    this.currentUserSignal.set(user);
  }

  clearUser(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.currentUserSignal.set(null);
  }

  getToken(): string | null {
    return this.currentUserSignal()?.token ?? null;
  }

  private loadUser(): CurrentUser | null {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    try {
      const user = JSON.parse(stored) as CurrentUser;
      if (!user?.token || this.isTokenExpired(user.token)) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      return user;
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  }

  private isTokenExpired(token: string): boolean {
    try {
      const payload = token.split('.')[1];
      const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
      if (typeof decoded.exp !== 'number') return true;
      // exp είναι Unix timestamp σε δευτερόλεπτα
      return Date.now() >= decoded.exp * 1000;
    } catch {
      return true;
    }
  }
}
