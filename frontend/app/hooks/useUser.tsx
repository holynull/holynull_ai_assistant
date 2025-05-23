import { useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { getCookie, setCookie } from "../utils/cookies";
import { USER_ID_COOKIE_NAME } from "../utils/constants";

export function useUser() {
	const [userId, setUserId] = useState<string>();

	useEffect(() => {
		if (userId) return;

		const userIdCookie = getCookie(USER_ID_COOKIE_NAME);
		if (userIdCookie) {
			setUserId(userIdCookie);
		} else {
			const newUserId = "64ce867f-8adc-423e-93ce-437f0a38fe6b";//uuidv4();
			setUserId(newUserId);
			setCookie(USER_ID_COOKIE_NAME, newUserId);
		}
	}, []);

	return {
		userId,
	};
}
