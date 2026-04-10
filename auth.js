const SUPABASE_URL = "https://tlyioijsopxeegzfjlqe.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_AdEHgXPGJ2gKGVAjb7RYSg_YzUuT6jB";

const _supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

window.SsobigAuth = {
  async signIn() {
    const { error } = await _supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        queryParams: { hd: "ssobig.com" },
        redirectTo: window.location.origin + window.location.pathname,
      },
    });

    if (error) {
      console.error("signIn error:", error.message);
    }
  },

  async signOut() {
    await _supabase.auth.signOut();
    window.location.reload();
  },

  async getSession() {
    const { data } = await _supabase.auth.getSession();
    return data.session;
  },

  async getUser() {
    const { data } = await _supabase.auth.getUser();
    return data.user;
  },

  isSsobigEmail(email) {
    return typeof email === "string" && email.endsWith("@ssobig.com");
  },

  onAuthStateChange(callback) {
    return _supabase.auth.onAuthStateChange((event, session) => {
      callback(event, session);
    });
  },

  waitForSession() {
    return new Promise((resolve) => {
      const {
        data: { subscription },
      } = _supabase.auth.onAuthStateChange((event, session) => {
        if (event === "INITIAL_SESSION") {
          subscription.unsubscribe();
          resolve(session);
        }
      });
    });
  },
};
