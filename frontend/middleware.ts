import { withAuth } from "next-auth/middleware"

export default withAuth({
  pages: {
    signIn: "/login",
  },
})

// Protect all dashboard and settings routes
export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*"],
}
