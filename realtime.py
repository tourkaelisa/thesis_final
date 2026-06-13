"""Real-time hub: ζωντανή ώθηση (push) στατιστικών στους συνδεδεμένους admins.

Κρατάει τα ενεργά WebSocket των διαχειριστών που βλέπουν το dashboard και,
όταν αλλάζουν τα δεδομένα συμπεριφοράς (π.χ. προσθήκη/αφαίρεση αγαπημένου),
τους στέλνει αμέσως φρέσκα στατιστικά — αντί να περιμένουν το περιοδικό polling.

Έτσι το dashboard γίνεται πραγματικά real-time: event-driven push πάνω από το
ίδιο WebSocket, με τις μετρικές να υπολογίζονται εκ νέου (GraphDB + SQLite)
μόνο όταν υπάρχει τουλάχιστον ένας admin να τις δει.
"""
from fastapi import WebSocket

import analytics


class DashboardHub:
    """Μητρώο ενεργών admin-συνδέσεων + broadcast των στατιστικών."""

    def __init__(self) -> None:
        self._admins: set[WebSocket] = set()

    def register(self, ws: WebSocket) -> None:
        """Καταχωρεί μια admin-σύνδεση ως συνδρομητή των live ενημερώσεων."""
        self._admins.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        """Αφαιρεί μια σύνδεση (στο κλείσιμο του WebSocket)."""
        self._admins.discard(ws)

    async def broadcast_stats(self) -> None:
        """Υπολογίζει μία φορά τα στατιστικά και τα ωθεί σε όλους τους admins.

        Αν δεν υπάρχει συνδεδεμένος admin, δεν γίνεται κανένας υπολογισμός
        (αποφυγή άσκοπου φόρτου στο GraphDB)."""
        if not self._admins:
            return
        message = {"type": "DASHBOARD_STATS", **analytics.get_dashboard_stats()}
        for ws in list(self._admins):
            try:
                await ws.send_json(message)
            except Exception:
                # Νεκρή σύνδεση — την αφαιρούμε σιωπηλά.
                self._admins.discard(ws)


hub = DashboardHub()
