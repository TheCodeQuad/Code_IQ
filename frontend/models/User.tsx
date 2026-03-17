import mongoose, { Schema, models, model } from "mongoose"

export interface IUser {
  name: string
  email: string
  password?: string
  provider?: string
  image?: string
  createdAt: Date
}

const UserSchema = new Schema<IUser>(
  {
    name: {
      type: String,
      required: [true, "Name is required"],
    },
    email: {
      type: String,
      required: [true, "Email is required"],
      unique: true,
    },
    password: {
      type: String,
      required: false,
    },
    provider: {
      type: String,
      default: "credentials",
    },
    image: {
      type: String,
    },
  },
  { timestamps: true }
)

const User = models.User || model<IUser>("User", UserSchema)

export default User