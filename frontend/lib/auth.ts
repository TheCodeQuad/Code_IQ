import { NextAuthOptions } from "next-auth";
import GitHubProvider from "next-auth/providers/github";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import connectDB from "@/lib/mongodb";
import User from "@/models/User";

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password are required");
        }

        await connectDB();

        const user = await User.findOne({ email: credentials.email });

        if (!user) {
          throw new Error("No user found with this email");
        }

        const isPasswordValid = await bcrypt.compare(
          credentials.password,
          user.password
        );

        if (!isPasswordValid) {
          throw new Error("Invalid password");
        }

        return {
          id: user._id.toString(),
          name: user.name,
          email: user.email,
        };
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google" || account?.provider === "github") {
        try {
          await connectDB();
          const existingUser = await User.findOne({ email: user.email });
          if (!existingUser) {
            const newUser = await User.create({
              name: user.name,
              email: user.email,
              image: user.image,
              provider: account.provider,
            });
            user.id = newUser._id.toString();
          } else {
            user.id = existingUser._id.toString();
          }
        } catch (error) {
          console.error("OAuth signIn error:", error);
          return false;
        }
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user?.id) {
        token.id = user.id;
      }

      // Backfill token.id for old/legacy sessions where id was not persisted.
      if (!token.id && token.email) {
        try {
          await connectDB();
          const dbUser = await User.findOne({ email: token.email }).select("_id");
          if (dbUser?._id) {
            token.id = dbUser._id.toString();
          }
        } catch (error) {
          console.error("JWT callback id backfill error:", error);
        }
      }

      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        let resolvedId = token.id as string | undefined;

        // Backfill during session creation if token is missing id but email exists.
        if (!resolvedId && session.user.email) {
          try {
            await connectDB();
            const dbUser = await User.findOne({ email: session.user.email }).select("_id");
            if (dbUser?._id) {
              resolvedId = dbUser._id.toString();
              if (resolvedId) {
                token.id = resolvedId;
              }
            }
          } catch (error) {
            console.error("Session callback id backfill error:", error);
          }
        }

        (session.user as any).id = resolvedId as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  secret: process.env.NEXTAUTH_SECRET,
};
